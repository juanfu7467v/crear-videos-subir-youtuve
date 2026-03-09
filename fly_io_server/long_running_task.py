import time
import generator
import uploader

def run(data):
    print(f"Starting processing for: {data.get('title')}")
    try:
        video_path = generator.generate_video(data)
        uploader.upload_to_youtube(video_path, data)
        print("Process completed successfully")
    except Exception as e:
        print(f"Error processing video: {e}")
