print("starting...")

from time import sleep
import grovepi
from azure.storage.blob import BlockBlobService, PublicAccess, ContentSettings
from picamera import PiCamera
import datetime
import json
import os

print("functions...")
# - this is specific to the Azure blob created for the demo
def copy_to_blob (file_long_name, file_name):
    block_blob_service = BlockBlobService(account_name=azure_blob_account, account_key=azure_blob_account_key)
    block_blob_service.create_blob_from_path(
        azure_blob_container,
        file_name,
        file_long_name,
        content_settings=ContentSettings(content_type='image/png')
        )

def capture_image(file_name):
    camera = PiCamera(resolution = (2048, 1536))
    #camera.exposure_mode = 'auto'
    camera.rotation = 180
    camera.capture(file_name)
    camera.close()


def file_cleanup():
    for dirpath, dirnames, filenames in os.walk(camera_image_folder):
        for file in filenames:
            curpath = os.path.join(dirpath, file)
            file_mod = datetime.datetime.fromtimestamp(os.path.getmtime(curpath))
            if datetime.datetime.now() - file_mod > datetime.timedelta(hours=2):
                os.remove(curpath)

print("getting config...")

config_file = r"/home/pi/pi_config.json"

config_data = json.loads(open(config_file,'r').read())

azure_blob_account_key = config_data['configurations'][0]['azure_blob_account_key']
azure_blob_account = config_data['configurations'][1]['azure_blob_account']
azure_blob_container = config_data['configurations'][2]['azure_blob_container']
subscription_key = config_data['configurations'][3]['subscription_key']
endpoint_mscs = config_data['configurations'][4]['endpoint_mscs']
camera_image_folder = config_data['configurations'][5]['camera_image_folder']

print("variables...")
pir_sensor = 3
motion=0
grovepi.pinMode(pir_sensor,"INPUT")
cleanup_datetime = datetime.datetime.now()

print("running...")

while True:
    try:
        motion=grovepi.digitalRead(pir_sensor)
        if motion==1:
            now = datetime.datetime.now()
            camera_image_file_name = "motionpzero_"+now.strftime("%Y%m%d_%H%M%S")+".jpg"
            camera_image_full_name = camera_image_folder+"/"+camera_image_file_name
            print(camera_image_file_name)
            capture_image(camera_image_full_name)
            print("image saved")
            copy_to_blob(camera_image_full_name,camera_image_file_name)
            print("image stored to Azure")
            sleep(5)
        #print("nothing found")
        if datetime.datetime.now() - cleanup_datetime > datetime.timedelta(hours=2):
            #print("file cleanup")
            file_cleanup()
            cleanup_datetime = datetime.datetime.now()
        sleep(1)

    except IOError:
        camera.close()
        print ("Error")
    except KeyboardInterrupt:
        print("Goodbye")
        break
