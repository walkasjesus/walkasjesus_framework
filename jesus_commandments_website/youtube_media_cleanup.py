import csv
import os
from django.conf import settings
from jesus_commandments_website.settings import BASE_DIR
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Set the path to your Django project's settings module.
# This should be the Python import path to your settings module.
# Replace 'your_project_name' with your actual project name.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "jesus_commandments_website.settings")

# Initialize the YouTube Data API client
api_key = settings.YOUTUBE_API_KEY
youtube = build('youtube', 'v3', developerKey=api_key)

def is_valid_url(url):
    # Function to check if a URL is a valid YouTube URL
    try:
        video_id = None

        if 'youtube.com' in url or 'youtu.be' in url:
            if 'youtube.com' in url and 'v=' in url:
                video_id = url.split('v=')[1]
            elif 'youtube.com' in url and 'embed/' in url:
                video_id = url.split('embed/')[1]
            elif 'youtu.be' in url:
                video_id = url.split('/')[-1]

            if video_id:
                video_details = youtube.videos().list(id=video_id, part="snippet,status").execute()
                if len(video_details.get('items', [])) > 0:
                    status = video_details["items"][0]["status"]["privacyStatus"]
                    if status == "public":
                        return True
                    else:
                        print(f"Video {url} has status: {status}")
                else:
                    print(f"Video {url} marked for removal")
        else:
            # We do not parse non-YouTube URLs
            return True

    except HttpError as e:
        print(f"Error checking video accessibility for URL {url}: {e}")

    return False

def remove_invalid_media_csv(input_csv):
    with open(input_csv, 'r', newline='', encoding='utf-8') as input_file:
        csv_reader = csv.DictReader(input_file, delimiter=';')
        fieldnames = csv_reader.fieldnames

        rows_to_keep = []

        for row in csv_reader:
            video_url = row['media_url']
            if not video_url:
                # If there's no video URL, keep the row
                rows_to_keep.append(row)
            elif is_valid_url(video_url):
                # Keep the row if the URL is a valid YouTube URL
                rows_to_keep.append(row)

    # Reopen the CSV file in write mode and write only the rows to keep
    with open(input_csv, 'w', newline='', encoding='utf-8') as output_file:
        csv_writer = csv.DictWriter(output_file, fieldnames=fieldnames, delimiter=';')
        csv_writer.writeheader()
        csv_writer.writerows(rows_to_keep)


if __name__ == '__main__':
    input_csv_file = os.path.join(BASE_DIR, 'data', 'media', 'media.csv')
    remove_invalid_media_csv(input_csv_file)
