import json
import time
import random
import os
import asyncio
from apify import Actor
from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp
from seleniumwire import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


async def get_transcript_api(video_id):
    """Try fetching transcript via YouTube API"""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return json.dumps(transcript, indent=2)
    except Exception as e:
        Actor.log.info(f"API Method Failed: {e}")
        return None


async def get_transcript_yt_dlp(video_id):
    """Fallback to yt-dlp with Apify Proxy"""
    try:
        ydl_opts = {
            'quiet': True,
            'proxy': 'http://proxy.apify.com:8000',  # Using Apify Proxy
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            return json.dumps(info.get('automatic_captions', {}), indent=2)
    except Exception as e:
        Actor.log.info(f"yt-dlp Failed: {e}")
        return None


async def get_transcript_selenium(video_id):
    """Use Selenium to extract transcript if everything else fails"""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280x720")

    driver = webdriver.Chrome(options=options)
    driver.get(f"https://www.youtube.com/watch?v={video_id}")

    try:
        # Wait for transcript button
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "ytp-subtitles-button"))
        )
        element.click()

        # Wait for captions
        time.sleep(random.uniform(5, 10))
        transcript = driver.page_source
        return transcript
    except Exception as e:
        Actor.log.info(f"Selenium Failed: {e}")
        return None
    finally:
        driver.quit()


async def main():
    """Main Apify Actor function"""
    await Actor.init()  # Ensure Actor is initialized properly

    input_data = await Actor.get_input() or {}
    # Extract video ID from start_urls
    start_urls = input_data.get("start_urls", [])
    video_id = None

    if start_urls:
        first_url = start_urls[0].get("url", "")
        if "watch?v=" in first_url:
            video_id = first_url.split("watch?v=")[-1].split("&")[0]  # Extract video ID

    if not video_id:
        Actor.log.error("No video_id provided!")
        return


    if not video_id:
        Actor.log.error("No video_id provided!")
        return

    transcript = (
        await get_transcript_api(video_id) or
        await get_transcript_yt_dlp(video_id) or
        await get_transcript_selenium(video_id)
    )


    if transcript:
        Actor.log.info("Transcript Extracted Successfully!")

        # Save transcript to Apify storage
        await Actor.set_value("OUTPUT", transcript)  # Saves in Apify storage
        Actor.log.info("Transcript saved in Apify storage as OUTPUT.json")

        # Explicitly save transcript to local file system
        output_path = "apify_storage/key_value_stores/default/OUTPUT.json"
        os.makedirs(os.path.dirname(output_path), exist_ok=True)  # Ensure the directory exists

        with open(output_path, "w") as f:
            json.dump(transcript, f, indent=2)

        Actor.log.info(f"Transcript explicitly saved to {output_path}")

    else:
        Actor.log.error("Failed to extract transcript")

    await Actor.exit()



# Run Apify Actor correctly
if __name__ == "__main__":
    asyncio.run(main())
