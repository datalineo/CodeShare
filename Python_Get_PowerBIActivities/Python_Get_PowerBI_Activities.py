import logging
import os
import azure.functions as func
from azure.identity import ClientSecretCredential
from azure.storage.blob import BlobClient
from azure.keyvault.secrets import SecretClient
import datetime
import requests
import json


def main(req: func.HttpRequest) -> func.HttpResponse:
    
    # Grab keys, set variables
    logging.info('Azure Function App: get_powerbi_usage triggered')
    keyvault_uri = 'https://mykeyvaultname.vault.azure.net/'
    client_id = os.environ['DatalineoAdminAppRegClientID']
    client_secret = os.environ['DatalineoAdminAppRegClientSecret']
    tenant_id = os.environ['DatalineoTenantID']
    blob_url_format = 'https://myblobtaontainer.blob.core.windows.net/powerbiusage/datalineo_powerbi_usage_{0}.json{1}'
    powerbi_api_scope = 'https://analysis.windows.net/powerbi/api/.default'

    # Usage API only returns data for max 24 hour period
    # this process will go back three days, and call the REST API 3 times, just in case a previous day was missed
    today = datetime.datetime.combine(datetime.date.today(), datetime.time(0,0,0,0))
    start_date = (today - datetime.timedelta(3))
    end_date = start_date + datetime.timedelta(seconds=(24*60*60)-1)

    # Create a credential for authenticating to Azure KeyVault, and to grab a token for Power BI REST API
    client_credential_class = ClientSecretCredential(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)
    access_token_class = client_credential_class.get_token(powerbi_api_scope)
    access_token = access_token_class.token
    header = {
        'Content-Type':'application/json',
        'Authorization': f'Bearer {access_token}'
        }

    # create a client connection to Azure Keyvault
    secret_client = SecretClient(vault_url=keyvault_uri, credential=client_credential_class)
    blob_sas_token = secret_client.get_secret('LineoInternalSasToken').value

    # loop for the three days to call the REST API
    while start_date < today:
        logging.info('get_powerbi_usage:{0}'.format(start_date))
        # set the start/end date times to 00:00:00 and 23:59:59 for the current date
        params = {'startDateTime':"'" + start_date.isoformat() + "'",'endDateTime':"'" + end_date.isoformat() + "'",}
        response = requests.get('https://api.powerbi.com/v1.0/myorg/admin/activityevents', headers=header, params=params)

        if response.status_code != 200:
            logging.info('get_powerbi_usage function error:{0}, {1}'.format(response.status_code, response.text))
        else:
            # get the api response & the activity event data
            response_json = response.json()
            activity_events = response_json['activityEventEntities']
            # the response in pages, and includes a continuation uri for additional activity data
            while response_json['continuationUri']:
                continue_uri = response_json['continuationUri']
                response = requests.get(continue_uri, headers=header)
                if response.status_code != 200:
                    logging.info('get_powerbi_usage function error:{0}, {1}'.format(response.status_code, response.text))
                else:
                    response_json = response.json()
                    activity_data = response_json['activityEventEntities']
                    # sometimes the continuation uri is an empty list, check its length & append it
                    if len(activity_data) > 0: 
                        activity_events.append(activity_data)

            # set up the url to an Azure Blob file, with the date format & SAS Token to authenticate
            # create a connection to the file, then load the data, overwrite if necessary
            blob_url = blob_url_format.format(start_date.strftime('%Y%m%d'),blob_sas_token)
            blob_client = BlobClient.from_blob_url(blob_url)
            blob_client.upload_blob(json.dumps(activity_events), overwrite=True)

        # add another day to continue the loop
        start_date += datetime.timedelta(1)
        end_date += datetime.timedelta(1)

    # standard Azre Functions HTTP response
    return func.HttpResponse(
             'Function complete. you can close this window',
             status_code=200
        )
