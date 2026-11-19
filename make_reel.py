import os
import re
import random
import asyncio
import textwrap
import requests
import edge_tts
from PIL import Image, ImageDraw, ImageFont
from deep_translator import GoogleTranslator
from moviepy.editor import (
    ImageClip, AudioFileClip, CompositeVideoClip,
    CompositeAudioClip, concatenate_videoclips
)

def get_fact_sentences():
    try:
        res = requests.get("https://jsph.pl", timeout=10).json()
        hindi_fact = GoogleTranslator(source='en', target='hi').translate(res["text"])
        full_text = f"क्या आप जानते हैं? {hindi_fact}"
    except Exception:
        full_text = "क्या आप जानते हैं? अंतरिक्ष में दो धातु के टुकड़े एक-दूसरे को छूते ही हमेशा के लिए जुड़ जाते हैं। इसे कोल्ड वेल्डिंग कहा जाता है।"

    sentences = [s.strip() for s in re.split(r'(?<=[।?!.])\s+', full_text) if len(s.strip()) > 3]
    return sentences if sentences else [full_text]

def fetch_visual_clip(index, duration):
    topics = ["space galaxy", "earth universe", "mysteries science", "nature mountains", "ocean deep", "stars night"]
    query = random.choice(topics)
    img_path = f"bg_{index}.jpg"
    try:
        wiki_url = f"https://wikimedia.org{query}&gsrnamespace=6&gsrlimit=20&prop=imageinfo&iiprop=url&format=json"
        headers = {"User-Agent": "FreeReelBot/2.0"}
        pages = requests.get(wiki_url, headers=headers, timeout=10).json().get("query", {}).get("pages", {})
        urls = [
            p["imageinfo"]["url"] for p in pages.values()
            if "imageinfo" in p and p["imageinfo"]["url"].lower().endswith((".jpg", ".jpeg", ".png"))
        ]
        if urls:
            with open(img_path, "wb") as f:
                f.write(requests.get(random.choice(urls), headers=headers, timeout=15).content)
            Image.open(img_path).convert("RGB").resize((1200, 2133)).save(img_path)
            return (
                ImageClip(img_path)
                .set_duration(duration)
                .resize(lambda t: 1 + 0.05 * t)
                .set_position(("center", "center"))
            )
    except Exception:
        pass

    Image.new("RGB", (1080, 1920), (15, 23, 42)).save(img_path)
    return ImageClip(img_path).set_duration(duration)

def make_subtitle_layer(text, duration):
    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 105))
    draw = ImageDraw.Draw(img)
    font_path = "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"
    font = ImageFont.truetype(font_path, 60) if os.path.exists(font_path) else ImageFont.load_default()

    lines = textwrap.wrap(text, width=25)
    y_text = 750
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox - bbox
        x_text = (1080 - text_width) / 2
        draw.text((x_text + 3, y_text + 3), line, font=font, fill=(0, 0, 0, 230))
        draw.text((x_text, y_text), line, font=font, fill=(255, 255, 255, 255))
        y_text += 85

    sub_path = f"sub_{random.randint(1000,9999)}.png"
    img.save(sub_path)
    return ImageClip(sub_path).set_duration(duration)

async def build_all_scenes(sentences):
    voice = random.choice(["hi-IN-MadhurNeural", "hi-IN-SwaraNeural"])
    scenes = []
    for i, sentence in enumerate(sentences):
        audio_path = f"voice_{i}.mp3"
        communicate = edge_tts.Communicate(sentence, voice, rate="+6%")
        await communicate.save(audio_path)

        voice_clip = AudioFileClip(audio_path)
        dur = voice_clip.duration + 0.2
        bg_clip = fetch_visual_clip(i, dur)
        sub_clip = make_subtitle_layer(sentence, dur)

        scene = CompositeVideoClip([bg_clip, sub_clip], size=(1080, 1920)).set_audio(voice_clip)
        scenes.append(scene)
    return concatenate_videoclips(scenes, method="compose")

final_video = asyncio.run(build_all_scenes(get_fact_sentences()))

if os.path.exists("music.mp3"):
    bg_music = AudioFileClip("music.mp3").volumex(0.12)
    if bg_music.duration < final_video.duration:
        bg_music = bg_music.audio_loop(duration=final_video.duration)
    else:
        bg_music = bg_music.subclip(0, final_video.duration)
    final_video = final_video.set_audio(CompositeAudioClip([final_video.audio, bg_music]))

final_video.write_videofile("daily_fact_reel.mp4", fps=24, codec="libx264", audio_codec="aac")
