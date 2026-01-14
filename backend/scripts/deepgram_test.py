from deepgram import DeepgramClient
from env_vars import DEEPGRAM_API_KEY

dg = DeepgramClient(api_key=DEEPGRAM_API_KEY)

audio = dg.speak.v1.audio.generate(
    text="Hey Sakshi! This is Jin, I am your personal assistant. Do you need anything?",
    model="aura-2-odysseus-en",
)

with open("jin.wav", "wb") as f:
    for chunk in audio:
        f.write(chunk)
