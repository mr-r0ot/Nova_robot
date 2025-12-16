#!/usr/bin/env python3
"""
speak.py
خوندن متن آفلاین با pyttsx3

مثال‌ها:
  python speak.py "hi what's up?"
  python speak.py hi what's up?
  python speak.py --rate 150 "This is slower"
  python speak.py --save out.mp3 "Hello world"
  python speak.py --list-voices
"""

import sys
import argparse

try:
    import pyttsx3
except Exception as e:
    print("خطا: کتابخانه pyttsx3 نصب نیست.\nنصب کنید: pip install pyttsx3")
    sys.exit(1)

def list_voices(engine):
    voices = engine.getProperty('voices')
    for i, v in enumerate(voices):
        print(f"[{i}] id: {v.id}\n    name: {getattr(v, 'name', '')}\n    lang: {getattr(v, 'languages', '')}\n")
    print("برای انتخاب یکی از idها، از گزینه --voice-index استفاده کنید.")

def main():
    parser = argparse.ArgumentParser(description="Read aloud text (offline) using pyttsx3")
    parser.add_argument('text', nargs='*', help='Text to speak. If empty, reads from stdin.')
    parser.add_argument('--rate', type=int, default=200, help='Speech rate (default 200)')
    parser.add_argument('--volume', type=float, default=1.0, help='Volume 0.0-1.0 (default 1.0)')
    parser.add_argument('--voice-index', type=int, default=None, help='Choose voice by index from --list-voices')
    parser.add_argument('--list-voices', action='store_true', help='List available voices and exit')
    parser.add_argument('--save', type=str, default=None, help='Save spoken audio to file (e.g. out.wav or out.mp3)')
    args = parser.parse_args()

    engine = pyttsx3.init()
    if args.list_voices:
        list_voices(engine)
        return

    # متن را از آرگومان یا stdin بگیر
    if args.text:
        text = " ".join(args.text)
    else:
        # اگر کاربر متن نداده از stdin بخوان
        text = sys.stdin.read().strip()
        if not text:
            print("هیچ متنی دریافت نشد. متن را به عنوان آرگومان بدهید یا از stdin وارد کنید.")
            return

    # تنظیمات صدا
    engine.setProperty('rate', args.rate)
    # volume بین 0.0 تا 1.0
    vol = max(0.0, min(1.0, args.volume))
    engine.setProperty('volume', vol)

    # انتخاب voice اگر کاربر خواسته
    voices = engine.getProperty('voices')
    if args.voice_index is not None:
        if 0 <= args.voice_index < len(voices):
            engine.setProperty('voice', voices[args.voice_index].id)
        else:
            print("اندیس voice نامعتبر است. برای دیدن لیست از --list-voices استفاده کنید.")
            return

    try:
        if args.save:
            # تلاش برای ذخیره به فایل (قابل پشتیبانی در بسیاری از ران‌تایم‌ها)
            engine.save_to_file(text, args.save)
            engine.runAndWait()
            print(f"ذخیره شد: {args.save}")
        else:
            engine.say(text)
            engine.runAndWait()
    except Exception as e:
        print("خطا هنگام پخش/ذخیره صدا:", e)

if __name__ == "__main__":
    main()
