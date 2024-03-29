#!/usr/bin/env python3
"""
Imports python 3 packages from pypi.org
This Azure Automation runbook runs in Azure to import a package and its dependencies from pypi.org.
It requires the subscription id, resource group of the Automation account, Automation name, and package name as arguments.
Args:
    subscription_id (-s) - Subscription id of the Automation account
    resource_group (-g) - Resource group name of the Automation account
    automation_account (-a) - Automation account name
    module_name (-m) - Name of module to import from pypi.org
    Imports module
    Example:
        import_python3package_from_pypi.py -s xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxx -g contosogroup -a contosoaccount -m pytz -v 1.0.0
Changelog:
    2020-12-29 AutomationTeam:
    -Import Python 3 package with dependencies
"""
import requests
import sys
import pip
import os
import re
import shutil
import json
import time
import getopt

#region Constants
PYPI_ENDPOINT = "https://pypi.org/simple"
FILENAME_PATTERN = "[\\w]+"
#endregion

def get_automation_msi_token():
    """ Returns a token that can be used to authenticate against Azure resources """
    import json

    # printing environment variables 
    endPoint = os.getenv('IDENTITY_ENDPOINT')+"?resource=https://management.azure.com/" 
    identityHeader = os.getenv('IDENTITY_HEADER') 
    payload={} 
    headers = { 
    'X-IDENTITY-HEADER': identityHeader,
    'Metadata': 'True' 
    } 
    response = requests.request("GET", endPoint, headers=headers, data=payload) 

    # Return the token
    return json.loads(response.text)['access_token']

def get_packagename_from_filename(packagefilename):
    match = re.match(FILENAME_PATTERN, packagefilename)
    return match.group(0)

def resolve_download_url(packagename, packagefilename):
    response = requests.get("%s/%s" % (PYPI_ENDPOINT, packagename))
    urls = re.findall(r'href=[\'"]?([^\'" >]+)', str(response.content))   
    for url in urls:
        if packagefilename in url:
            print ("Detected download uri %s for %s" % (url, packagename))
            return(url)

def send_webservice_import_module_request(packagename, download_uri_for_file):
    request_url = "https://management.azure.com/subscriptions/%s/resourceGroups/%s/providers/Microsoft.Automation/automationAccounts/%s/python3Packages/%s?api-version=2018-06-30" \
                  % (subscription_id, resource_group, automation_account, packagename)

    requestbody = { 'properties': { 'description': 'uploaded via automation', 'contentLink': {'uri': "%s" % download_uri_for_file} } }
    headers = {'Content-Type' : 'application/json', 'Authorization' : "Bearer %s" % token}
    r = requests.put(request_url, data=json.dumps(requestbody), headers=headers)
    print ("Request status for package %s was %s" % (packagename, str(r.status_code)))
    if str(r.status_code) not in ["200", "201"]:
        raise Exception("Error importing package {0} into Automation account. Error code is {1}".format(packagename, str(r.status_code)))

def make_temp_dir():
    destdir = os.path._getfullpathname("tempDownloadDir")
    if os.path.exists(destdir):
        shutil.rmtree(destdir)
    os.makedirs(destdir, 0o755)
    return destdir

def import_package_with_dependencies (packagename):
    # download package with all depeendencies
    download_dir = make_temp_dir()
    pip.main(['download', '-d', download_dir, packagename])
    for file in os.listdir(download_dir):
        pkgname = get_packagename_from_filename(file)
        download_uri_for_file = resolve_download_url(pkgname, file)
        send_webservice_import_module_request(pkgname, download_uri_for_file)
        # Sleep a few seconds so we don't send too many import requests https://docs.microsoft.com/en-us/azure/azure-subscription-service-limits#automation-limits
        time.sleep(10)

if __name__ == '__main__':
    if len(sys.argv) < 9:
        raise Exception("Requires Subscription id -s, Automation resource group name -g, account name -a, and module name -g as arguments. \
                        Example: -s xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxx -g contosogroup -a contosoaccount -m pytz ")

    # Process any arguments sent in
    subscription_id = None
    resource_group = None
    automation_account = None
    module_name = None

    opts, args = getopt.getopt(sys.argv[1:], "s:g:a:m:")
    for o, i in opts:
        if o == '-s':  
            subscription_id = i
        elif o == '-g':  
            resource_group = i
        elif o == '-a': 
            automation_account = i
        elif o == '-m': 
            module_name = i

    # Set Run as token for this automation accounts service principal to be used to import the package into Automation account
    token = get_automation_msi_token()

    # Import package with dependencies from pypi.org
    import_package_with_dependencies(module_name)
    print ("\nCheck the python 3 packages page for import status...")
