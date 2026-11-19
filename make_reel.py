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

# बिना किसी API Key के सीधे असली HD फ़ोटो लाना और उन पर स्मूथ ज़ूम एनिमेशन लगाना
def fetch_animated_visual(index, duration):
    topics = ["Nebula", "Galaxy", "Earth_from_space", "Aurora_borealis", "Milky_Way", "Deep_ocean", "Volcano", "Lightning"]
    query = random.choice(topics)
    img_path = f"bg_{index}.jpg"
    downloaded = False

    try:
        wiki_url = f"https://wikipedia.org{query}&gsrlimit=10&prop=pageimages&pithumbsize=1080&format=json"
        headers = {"User-Agent": "HindiFactReelBot/3.0 (contact@example.com)"}
        pages = requests.get(wiki_url, headers=headers, timeout=10).json().get("query", {}).get("pages", {})
        img_urls = [p["thumbnail"]["source"] for p in pages.values() if "thumbnail" in p]
        if img_urls:
            chosen_url = random.choice(img_urls)
            img_data = requests.get(chosen_url, headers=headers, timeout=15).content
            with open(img_path, "wb") as f:
                f.write(img_data)
            # फ़ोटो को वर्टिकल (9:16) आकार में फिट करें
            im = Image.open(img_path).convert("RGB")
            im = im.resize((1300, 2300))
            im.save(img_path)
            downloaded = True
    except Exception:
        pass

    if not downloaded:
        # अगर किसी कारण इंटरनेट से फ़ोटो न आए, तो गहरा नीला-बैंगनी ग्रेडिएंट बैकग्राउंड बनाएं
        im = Image.new("RGB", (1300, 2300), (18, 25, 48))
        im.save(img_path)

    # असली वीडियो जैसा स्मूथ ज़ूम-इन एनिमेशन (Ken Burns Effect)
    clip = (
        ImageClip(img_path)
        .set_duration(duration)
        .resize(lambda t: 1.0 + 0.08 * (t / max(duration, 1)))
        .set_position(("center", "center"))
    )
    return clip

def make_subtitle_layer(text, duration):
    img = Image.new("RGBA", (1080, 1920), (0, 0, 0, 100))
    draw = ImageDraw.Draw(img)
    font_path = "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"
    font = ImageFont.truetype(font_path, 62) if os.path.exists(font_path) else ImageFont.load_default()

    # ऊपर एक आकर्षक हेडर पट्टी बनाएं
    draw.rectangle([(240, 280), (840, 360)], fill=(255, 204, 0, 255))
    header_font = ImageFont.truetype(font_path, 42) if os.path.exists(font_path) else font
    draw.text((340, 295), "रोचक तथ्य (FACT)", font=header_font, fill=(0, 0, 0, 255))

    lines = textwrap.wrap(text, width=24)
    y_text = 760
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x_text = (1080 - text_width) / 2
        draw.text((x_text + 4, y_text + 4), line, font=font, fill=(0, 0, 0, 240))
        draw.text((x_text, y_text), line, font=font, fill=(255, 255, 255, 255))
        y_text += 92

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
        dur = voice_clip.duration + 0.25
        bg_clip = fetch_animated_visual(i, dur)
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
