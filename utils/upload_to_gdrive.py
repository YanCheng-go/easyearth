import argparse
import os
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import sys


def main(FILE_ID=None, shareable: bool = True, VERSION='', format='.zip') -> (str, bool):
    """Upload or update a ZIP file in Google Drive using service account credentials.

    Args:
        FILE_ID (str): If provided, updates the existing file with this ID. Otherwise, creates a new file.
        shareable (bool): If True, ensures the file is shareable by anyone with the link.
        VERSION (str): Version suffix to append to the file name. Empty string for final version.

    Returns:
        file_id (str): The ID of the uploaded/updated file.
        is_shareable (bool): Whether the file is shareable after this operation.
    """

    if VERSION != '':
        FILE_ID = None  # Reset FILE_ID for testing or new uploads

    # Load credentials from environment variable
    creds_json = os.environ['GDRIVE_CREDENTIALS']
    creds_dict = json.loads(creds_json)

    SCOPES = ['https://www.googleapis.com/auth/drive']
    credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

    drive_service = build('drive', 'v3', credentials=credentials)

    file_metadata = {'name': f'easyearth_env{VERSION}{format}',}
    media = MediaFileUpload(f'easyearth_env{VERSION}{format}', mimetype='application/gzip' if format == '.zip' else 'application/zip')

    if FILE_ID is None:
        # Create a new file
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        FILE_ID = file.get('id')
        print(f'Uploaded new ZIP file to Google Drive! File ID: {FILE_ID}')
    else:
        # Update existing file
        file = drive_service.files().update(
            fileId=FILE_ID,
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        print(f'Updated ZIP file in Google Drive! File ID: {FILE_ID}')

    # Check if the file is already shareable
    permissions = drive_service.permissions().list(fileId=FILE_ID).execute()
    is_shareable = any(
        perm.get('role') == 'reader' and perm.get('type') == 'anyone'
        for perm in permissions.get('permissions', [])
    )
    print(f'File {FILE_ID} is currently {"shareable" if is_shareable else "not shareable"}.')

    # If not shareable and requested, make it shareable
    if shareable and not is_shareable:
        drive_service.permissions().create(
            fileId=FILE_ID,
            body={'role': 'reader', 'type': 'anyone'}
        ).execute()
        print(f'File {FILE_ID} is now shareable.')

    # Generate the shareable link
    shareable_link = f"https://drive.google.com/file/d/{FILE_ID}/view?usp=sharing"
    print(f'Shareable link: {shareable_link}')

    return FILE_ID, is_shareable or shareable


if __name__ == '__main__':
    # main(FILE_ID='1FXmE_R1ZRoH3IHzv139stxNywB3HfgXo', shareable=True, VERSION='', format='.zip')  # Replace with your Google Drive file ID if updating an existing file
    # main(FILE_ID='1RBv2I_30fwNGwqvBAL31vr4HO5KUbXQc', shareable=True, VERSION='', format='.tar')  # Windows tar file
    # main(FILE_ID=None, shareable=True, VERSION='', format='.zip')  # For testing or new uploads

    parser = argparse.ArgumentParser(description="Upload a file to Google Drive")
    parser.add_argument("--file-id", required=False, help="Google Drive file ID to update (if any)", type=str, default=None)
    parser.add_argument("--shareable", required=False, help="Make the file shareable by anyone with the link", action='store_true', default=True)
    parser.add_argument("--VERSION", required=False, help="Version suffix to append to the file name", type=str, default='')
    parser.add_argument("--format", required=False, help="File format to upload (e.g., .zip, .tar)", type=str, default='.zip')
    args = parser.parse_args()

    main(FILE_ID=args.file_id, shareable=args.shareable, VERSION=args.VERSION, format=args.format)

