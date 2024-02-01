import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import config
from datetime import datetime

CLIENT_SECRET_FILE = 'client_secret.json'
API_NAME = 'drive'
API_VERSION = 'v3'
SCOPES = ['https://www.googleapis.com/auth/drive.file']


def authenticate():
    credentials = None
    if os.path.exists('token.json'):
        credentials = Credentials.from_authorized_user_file('token.json')
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            credentials = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(credentials.to_json())
    return build(API_NAME, API_VERSION, credentials=credentials)


def create_or_get_folder(folder_name, parent_folder_id, drive_service):
    results = drive_service.files().list(
        q=f"'{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and name='{folder_name}'"
    ).execute()
    folders = results.get('files', [])

    if not folders:
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_folder_id]
        }
        folder = drive_service.files().create(body=folder_metadata, fields='id').execute()
        return folder['id']
    else:
        return folders[0]['id']


def upload_folder(folder_path, parent_folder_id, drive_service):
    folder_name = os.path.basename(folder_path)
    today_date = datetime.today().strftime('%Y-%m-%d')
    drive_folder_name = folder_name + '_' + today_date
    folder_id = create_or_get_folder(drive_folder_name, parent_folder_id, drive_service)

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        media = MediaFileUpload(file_path)
        drive_service.files().create(body={'name': filename, 'parents': [folder_id]}, media_body=media).execute()


def backup_multiple_folders(folder_paths, service):
    for folder_path in folder_paths:
        upload_folder(folder_path, config.FOLDER_ID, service)
        print(f'Backup for folder {folder_path} completed.')
        

def delete_old_backups(service):
    results = service.files().list(q=f"'{config.FOLDER_ID}' in parents and mimeType='application/vnd.google-apps.folder'").execute()
    folders = results.get('files', [])

    if not folders:
        print('No folders found.')
    else:
        for folder in folders:
            folder_id = folder['id']
            folder_name = folder['name']
            print(f'Folder name: {folder_name}')

            # Get the list of files (backups) in the folder
            backups_results = service.files().list(q=f"'{folder_id}' in parents").execute()
            backups = backups_results.get('files', [])

            if not backups:
                print(f'No backups found in folder: {folder_name}')
            else:
                for backup in backups:
                    backup_name = backup['name']
                    print(f'Backup name: {backup_name}')

                    date_string = backup_name.split('_')[-1]
                    backup_date = datetime.strptime(date_string, '%Y-%m-%d')

                    # Check if the backup is older than 2 days
                    if (datetime.today() - backup_date).days > 2:
                        service.files().delete(fileId=backup['id']).execute()
                        print(f'Deleted old backup: {backup_name} in folder: {folder_name}')


if __name__ == '__main__':
    drive_service = authenticate()

    for folder in config.FOLDER_LIST:
        backup_folder_name = os.path.basename(folder) + "_Backup"
        backup_folder_id = create_or_get_folder(backup_folder_name, config.FOLDER_ID, drive_service)
        upload_folder(folder, backup_folder_id, drive_service)
        print(f'Backup for folder {folder} completed.')

    delete_old_backups(drive_service)