from datetime import datetime
import meraki
import sys
import argparse
import time
import os
import signal
from dotenv import load_dotenv
from pathlib import Path
import re

def input_org_name():
    while True:
        print('\n' + ("*" * 70))
        print('\n - Please remember to check your spelling.  The organization name is case sensitive.')
        org_name = input(' - Enter the name of the organization to create/modify: ')
        confirm = input(f' - Please confirm "{org_name}" is valid with y or n:  ').lower()
        if confirm.startswith('y'):
            return org_name
        elif confirm.lower() == 'help':
            printhelp()


def verify_acct_name():
    while True:
        print('\n' + ("*" * 70))
        print('\n - Account numbers must be 8 characters in length and #s only.')
        acct = input(' - Enter the account number to be used for the SAML role: ')
        if len(acct) == 8 and acct.isdigit():
            confirm = input(f' - Please confirm "{acct}" is valid with y or n:  ').lower()
            if confirm.startswith('y'):
                return acct


def update_org_saml(org_id, acct):
    # First identify the saml roles in place and define the account role and id
    roles = dashboard.organizations.getOrganizationSamlRoles(org_id)
    for account in roles:
        saml_role = account['role']
        saml_id = account['id']
        if 'ACCT' not in saml_role:
            continue
        else:
            saml_role = saml_role.replace('07633567', acct)
            print(f'\n - SAML role to be updated to: {saml_role}')
            try:
                dashboard.organizations.updateOrganizationSamlRole(org_id, saml_id, role=saml_role)
                print(' - Updated SAML role')
            except meraki.APIError as e:
                print(' - Failed to update SAML role\n')
                print(f'Meraki API error: {e}')
                continue
            except Exception as e:
                print(' - Failed to update SAML role\n')
                print(f'Some other error: {e}')
                continue


def input_network_info(org):
    name = verify_network_name()
    if "'" in name:
        name = name.replace("'", "")
    if '"' in name:
        name = name.replace('"', '')

    try:
        # Check to see if the network already exists in the organization.  If yes, use the existing network ID.
        networks = dashboard.organizations.getOrganizationNetworks(org)
    except meraki.APIError:
        print('API error. Please re-try again.  Program will exit.')
        printhelp()
        finish(2)
    if not networks:
        try:
            print(f'\n - Network does not exist, proceeding with creation of "{name}"')
            time.sleep(.1)
            nw_id = create_network(org, name)
            update_snmp(nw_id)
            update_alerts(nw_id)
        except meraki.APIError:
            print('API error. Please re-try again.  Program will exit.')
            printhelp()
            finish(2)
    else:
        for network in networks:
            if network['name'].upper() == name.upper() and len(networks) > 0:
                nw_id = network['id']
                print(f'\n - "{name}" already exists.  Network ID: {nw_id[2:]}')
                continue
            else:
                try:
                    print(f'\n - Network does not exist, proceeding with creation of "{name}"')
                    time.sleep(.2)
                    nw_id = create_network(org, name)
                    update_snmp(nw_id)
                    update_alerts(nw_id)
                    break
                except meraki.APIError:
                    print('API error. Please re-try again.  Program will exit.')
                    printhelp()
                    finish(2)

network_pattern = '^([A-Z]{4}(AK|AL|AR|AZ|CA|CO|CT|DC|DE|FL|GA|HI|IA|ID|IL|IN|KS|KY|LA|MA|MD|ME|MI|MN|MO|MS|MT|NC|ND|NE|NH|NJ|NM|NV|NY|OH|OK|OR|PA|PR|RI|SC|SD|TN|TX|UT|VA|VT|WA|WI|WV|WY)[A-Z][0-9]{2})$'
def verify_network_name():
    while True:
        clli = input('\nEnter site\'s CLII:  ')
        if len(clli) == 8:
            clli = clli.upper()
            g = re.match(pattern, ccli).groups()
            if g and g[0]:
                address = input('Enter site\'s street address:  ')
                network_name = clli + ' - ' + address
                confirm = input(f'Please confirm "{network_name}" is valid with y or n:  ').lower()
                if confirm.startswith('y'):
                    return network_name
            else:
                print('You entered invalid CLII, please try again: ')

# Create networks. Function can be repeatably called to create multiple sites.
def create_network(org_id, name):
    time.sleep(.1)
    timezone = get_timezone(name)
    producttypes = ['appliance', 'camera', 'cellularGateway', 'environmental', 'switch', 'wireless']
    try:
        network_details = dashboard.organizations.createOrganizationNetwork(org_id, name=name, timezone=timezone,
                                                                            productTypes=producttypes)
        nw_id = network_details['id']
        dashboard.networks.updateNetwork(nw_id, timeZone=timezone)

        print(f' - Network: "{name}" created | Network ID: {nw_id[2:]}')
        return nw_id
    except meraki.APIError as e:
        print(f'Meraki API error: {e}')
        printhelp()
        finish(2)

# Selects appropriate timezone based on CLLI
def get_timezone(val):
    state = val[4:6].upper()
    selected_timezone = None
    timezones = {
        'EST': ['CT', 'DE', 'FL', 'GA', 'KY', 'ME', 'MD', 'MA', 'MI', 'NH', 'NJ', 'NY',
                'NC', 'OH', 'PA', 'RI', 'SC', 'VT', 'VA', 'WV'],
        'CST': ['AL', 'AR', 'IL', 'IA', 'LA', 'MN', 'MS', 'MO', 'OK', 'TN', 'TX', 'WI'],
        'SST': ['AZ'],
        'MST': ['CO', 'KS', 'MT', 'NE', 'NM', 'ND', 'SD', 'UT', 'WY'],
        'PST': ['CA', 'ID', 'NV', 'OR', 'WA'],
        'HST': ['AK', 'HI'],
    }

    # Iterate through dictionary values and select timezone if state exists
    for timezone in timezones:
        if state in timezones[timezone]:
            selected_timezone = timezone

    # Return correct timezone if it is found, default to EST if not found
    if selected_timezone == 'EST':
        return 'America/New_York'
    elif selected_timezone == 'CST':
        return 'America/Chicago'
    elif selected_timezone == 'SST':
        return 'US/Arizona'
    elif selected_timezone == 'MST':
        return 'America/Denver'
    elif selected_timezone == 'PST':
        return 'America/Los_Angeles'
    elif selected_timezone == 'HST':
        return 'Pacific/Honolulu'
    else:
        print(f'\nYour entry has an invalid state code for the CLLI.\n'
              f'Your entry shows "{state}" which is not a state code.\n'
              f'Timezone will default to EST.\n')
        return 'America/New_York'

def update_alerts(network):
    # These are the standard network level alerts using the same values as "*Spectrum Clone"
    alerts = [
        {
            'type': 'applianceDown',
            'enabled': True,
            'alertDestinations': {
                'emails': [],
                'snmp': True,
                'allAdmins': False,
                'httpServerIds': []
            },
            'filters': {'timeout': 10}
        },
        {
            'type': 'failoverEvent',
            'enabled': True,
            'alertDestinations': {
                'emails': [],
                'snmp': True,
                'allAdmins': False,
                'httpServerIds': []
            },
            'filters': {}
        },
        {
            'type': 'dhcpNoLeases',
            'enabled': False,
            'alertDestinations': {
                'emails': [],
                'snmp': False,
                'allAdmins': False,
                'httpServerIds': []
            },
            'filters': {}
        },
        {
            'type': 'vrrp',
            'enabled': True,
            'alertDestinations': {
                'emails': [],
                'snmp': True,
                'allAdmins': False,
                'httpServerIds': []
            },
            'filters': {}
        },
        {
            'type': 'cellularGatewayDown',
            'enabled': True,
            'alertDestinations': {
                'emails': [],
                'snmp': True,
                'allAdmins': False,
                'httpServerIds': []
            },
            'filters': {'timeout': 10}
        },
        {
            'type': 'powerSupplyDown',
            'enabled': True,
            'alertDestinations': {
                'emails': [],
                'snmp': True,
                'allAdmins': False,
                'httpServerIds': []
            },
            'filters': {}
        },
        {
            'type': 'rpsBackup',
            'enabled': True,
            'alertDestinations': {
                'emails': [],
                'snmp': True,
                'allAdmins': False,
                'httpServerIds': []
            },
            'filters': {}
        },
        {
            'type': 'udldError',
            'enabled': True,
            'alertDestinations': {
                'emails': [],
                'snmp': True,
                'allAdmins': False,
                'httpServerIds': []
            },
            'filters': {}
        },
        {
            'type': 'switchDown',
            'enabled': True,
            'alertDestinations': {
                'emails': [],
                'snmp': True,
                'allAdmins': False,
                'httpServerIds': []
            },
            'filters': {'timeout': 10}
        },
        {
            'type': 'gatewayDown',
            'enabled': True,
            'alertDestinations': {
                'emails': [],
                'snmp': True,
                'allAdmins': False,
                'httpServerIds': []},
            'filters': {'timeout': 10}
        },
        {
            'type': 'gatewayToRepeater',
            'enabled': True,
            'alertDestinations': {
                'emails': [],
                'snmp': True,
                'allAdmins': False,
                'httpServerIds': []
            },
            'filters': {}
        },
        {
            'type': 'repeaterDown',
            'enabled': True,
            'alertDestinations': {
                'emails': [],
                'snmp': True,
                'allAdmins': False,
                'httpServerIds': []
            },
            'filters': {'timeout': 10}
        }
    ]
    try:
        dashboard.networks.updateNetworkAlertsSettings(network, alerts=alerts)
        print(' - Successfully updated network alert settings')
    except meraki.APIError:
        print(' - Failed to update network alert settings')


def update_snmp(nw_id):
    users = [{'username': 'un1f13dMNE', 'passphrase': 'dmZadm1N'}]
    try:
        dashboard.networks.updateNetworkSnmp(nw_id, access='users', users=users)
        print(' - Successfully updated network SNMP settings.')
    except meraki.APIError:
        print(' - Failed to update SNMP network settings')


# Simple verification function
def verify(prompt):
    choice = input(prompt)
    if choice == 'y' or choice == 'yes':
        return True
    elif choice == 'n' or choice == 'no':
        return False
    else:
        verify('yes or no:  ')


def printusertext(p_message):
    # prints a line of text that is meant for the user to read
    # do not process these lines when chaining scripts
    print('@ %s' % p_message)


def printhelp():
    # Prints help text for users
    printusertext(
        '@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@')
    printusertext(
        'WARNING WARNING WARNING Unauthorized use of this script is strictly forbidden WARNING WARNING WARNING     @')
    printusertext(
        'This script is intended for MS Design and can be used to create organizations and networks for customers  @')
    printusertext(
        'Use this script to create a new organization and build the customer site(s) & network(s)                  @')
    printusertext(
        '                                                                                                          @')
    printusertext(
        'To run this simply execute it with your given alias or using the actual name of the python file           @')
    printusertext(
        'Account numbers are entered in as integers and must be exactly 8 characters in length                     @')
    printusertext(
        'Organization names are entered exactly how you enter them - it is case sensitive!                         @')
    printusertext(
        '                                                                                                          @')
    printusertext(
        ' - Notice: If no value is returned by the script:                                                         @')
    printusertext(
        ' - Check the organization name for spelling errors.                                                       @')
    printusertext(
        ' - Remember the organization name is case sensitive.                                                      @')
    printusertext(
        '                                                                                                          @')
    printusertext(
        ' - If you experience issues please reach out to a senior on your team for help.                           @')
    printusertext(
        ' - Please provide feedback and any improvement recommendations.                                           @')
    printusertext(
        '@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@')


def ctrl_c(sig, frame):
    finish(0)


def finish(status: int):
    end_time = datetime.now()
    print(f'\n' + ("*" * 70))
    print(f'\nScript complete, total runtime {end_time - start_time}')
    sys.exit(status)


def main():
    print('Starting program')
    org_name = input_org_name()
    org_id = None

    # Verify org name to be created does not exist
    time.sleep(.3)  # Slight delay to ensure org is seen if just created and script retriggered
    organizations = dashboard.organizations.getOrganizations()
    for org in organizations:
        check_name = org['name']
        check_org_id = org['id']
        if check_name == org_name:
            print(f'\n - Organization name: "{org_name}" already exists.')
            while verify('\nCreate new network for this organization? (y/n)  '):
                input_network_info(check_org_id)
            complete = input('\n*** Exit Program? ***:  Enter y or n: ').lower()
            if complete.startswith('y'):
                finish(0)
            else:
                print(
                    '\n**WARNING - By continuing you will trigger a new organization creation with the same name of '
                    'an existing org.')
                print('This is not allowed at this time. Orgs should not have the same name. Program terminating.')
                finish(0)

    # Clone existing organization and get new organization ID
    acct = verify_acct_name()
    print('\n' + ("*" * 70))
    template_org_info = dashboard.organizations.getOrganization(template_org_id)
    template_org_name = template_org_info['name']
    print(f'\n - Cloning from "{template_org_name}" to create new organization: "{org_name}"')
    try:
        org_info = dashboard.organizations.cloneOrganization(template_org_id, org_name)
        org_id = org_info['id']
        print(f' - Successfully created "{org_name}".  Organization ID: {org_id}')
    except meraki.APIError:
        print(f' - Failed to create: "{org_name}"')
        printhelp()
        finish(1)

    update_org_saml(org_id, acct)

    # Begin network creation
    print(f'\n' + ("*" * 70))
    print('\n - Network creation initializing.. Please read the instructions carefully'
          '\n - Enter the network name for this site as: "CLLI - Address".'
          '\n - CLLI must be 8 characters. (1-6 alphanumeric, 7-8 integers) | example: ASLDWI30 - 1500 10th St W')
    input_network_info(org_id)

    # If multiple new networks are needed the script will re-run create_network for the same organization
    while verify('\nCreate additional network? (y/n)  '):
        input_network_info(org_id)

    finish(0)


if __name__ == '__main__':
    # Identify the path for .env and import the key
    env_path = Path('.') / '.env'
    load_dotenv(dotenv_path=env_path)
    key = os.environ.get('key')     #This is designs key reference and should remain that way.
    signal.signal(signal.SIGINT, ctrl_c)

    # Define the template organization by ID.  Must match *Spectrum Clone in production.
    template_org_id = '615304299089499391'  # *Spectrum Clone ID - this is production code.

    # API call to Meraki dashboard
    dashboard = meraki.DashboardAPI(
        api_key=key,
        print_console=False,
        suppress_logging=True
    )

    start_time = datetime.now()
    parser = argparse.ArgumentParser(
        usage='%(prog)s [OPTION]...',
        description='Creates a new organization in the Meraki dashboard cloned from an existing organization.',
        epilog='''Notice: This script should only be used by MS Design and MS Fulfillment.
    If you continue to experience issues please reach out to a senior on your team for help.''')
    main()
