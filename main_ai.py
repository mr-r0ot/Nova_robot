import queue
import sounddevice as sd
import argparse
import json
import sys
import time

try:
    from vosk import Model, KaldiRecognizer
except Exception as e:
    print("خطا: کتابخانه 'vosk' نصب نیست. نصب کنید: pip install vosk")
    sys.exit(1)



def extract_direction_and_number(text: str):
    text = text.lower().strip()
    
    # نگاشت عددهای حروفی به عددی
    word_to_num = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10
    }

    # نگاشت جهت‌ها با واژگان مشابه
    directions = {
        "forward": ["forward", "ahead", "straight"],
        "backward": ["backward", "back", "behind"],
        "left": ["left"],
        "right": ["right"]
    }

    # جستجوی عدد در متن
    number = None
    for word, num in word_to_num.items():
        if word in text:
            number = num
            break

    # جستجوی جهت در متن
    direction_found = None
    for direction, keywords in directions.items():
        for keyword in keywords:
            if keyword in text:
                direction_found = direction
                break
        if direction_found:
            break

    # بررسی وجود "around"
    if "around" in text:
        return ["around",0]

    # بازگرداندن نتیجه در صورت وجود جهت و عدد
    if direction_found and number is not None:
        return [direction_found, number]
    elif direction_found:
        return [direction_found, 2]

    
    # در غیر این صورت None
    return None



from LexiDecay import LexiDecayModel
import os
creativity = 0.9
data = open('data.txt', encoding='utf-8').read().replace("\n",'')
modelx = LexiDecayModel()


n=0
for line in data.split('.'):
    modelx.add_category(line, line) # add tokens to model
    n+=1
print(f"=====load {n} token=====\n\n")





q = queue.Queue()

def _audio_callback(indata, frames, time_info, status):
    """sounddevice callback — داده خام را به صف می‌فرستد"""
    if status:
        # نمایش هشدارهای ورودی/دستگاه
        print(f"Audio status: {status}", file=sys.stderr)
    # indata در حالت raw استریمی 'int16' باید به bytes تبدیل شود
    q.put(bytes(indata))

def transcribe_from_mic(model_path: str, timeout: float = None, verbose: bool = True) -> str:
    """
    گوش دادن از میکروفن و بازگشت متن تشخیص داده‌شده.
    timeout: حداکثر ثانیه گوش دادن (None -> تا Ctrl+C)
    """
    # بارگذاری مدل
    try:
        model = Model(model_path)
    except Exception as e:
        raise RuntimeError(f"نمیتوان مدل را بارگذاری کرد از {model_path}. خطا: {e}")

    # نمونه‌برداری از دستگاه ورودی را بگیریم
    try:
        device_info = sd.query_devices(kind='input')
        samplerate = int(device_info['default_samplerate'])
    except Exception:
        samplerate = 16000  # اگر نتوان نمونه‌برداری پیش‌فرض را خواند، از 16000 استفاده کن

    # KaldiRecognizer را با samplerate تنظیم کن
    rec = KaldiRecognizer(model, samplerate)
    rec.SetWords(False)  # اگر خواستید اطلاعات زمان‌بندی کلمات را فعال کنید True بگذارید

    text_parts = []
    start_time = time.time()
    if verbose:
        print(f"[VOSK] Listening (samplerate={samplerate}). Press Ctrl+C to stop or wait timeout={timeout}.")

    try:
        # RawInputStream از sounddevice برای دریافت int16 mono
        with sd.RawInputStream(samplerate=samplerate, blocksize=8000, dtype='int16',
                               channels=1, callback=_audio_callback):
            while True:
                if timeout is not None and (time.time() - start_time) > timeout:
                    if verbose:
                        print("\nTimeout reached, finishing...")
                    break

                try:
                    data = q.get(timeout=0.5)
                except queue.Empty:
                    continue

                if rec.AcceptWaveform(data):
                    # یک جمله / عبارت نهایی تشخیص داده شد
                    res = json.loads(rec.Result())
                    part = res.get("text", "").strip()
                    if part:
                        text_parts.append(part)
                        if verbose:
                            print(">>", part)
                            out = modelx.classify(
                                part,
                                decay=creativity,
                                use_idf=True,
                                auto_common_reduce=True,
                                common_decay=0.6,
                                min_common_mult=0.08
                            )
                            print("Model Top token:\n", out["top"])
                            os.system(f'python speak.py "{out["top"][0]}" ')
                            m = (extract_direction_and_number(part))
                            print(m)
                            if m:
                                if m[0]=="right":
                                    try:
                                        os.system(f"python move.py --right {m[1]}")
                                    except:
                                        os.system(f"python move.py --right 2")
                                elif m[0]=="left":
                                    try:
                                        os.system(f"python move.py --left {m[1]}")
                                    except:
                                        os.system(f"python move.py --left 2")
                                elif m[0]=="forward":
                                    try:
                                        os.system(f"python move.py --left {m[1]} --right {m[1]}")
                                    except:
                                        os.system(f"python move.py --left 2 --right 2")
                                elif m[0]=="backward":
                                    try:
                                        os.system(f"python move.py --left -{m[1]} --right -{m[1]}")
                                    except:
                                        os.system(f"python move.py --left -2 --right -2")
                                elif m[0]=="around":
                                    os.system(f"python move.py --left -6")

                            time.sleep(3)

                        # اگر بخواهید فقط اولین عبارت را برگردانید می‌توانید اینجا break بگذارید
                    # ادامه بده تا چند عبارت جمع شود یا تا timeout/کنترل
                else:
                    # partial result — می‌توانید آن را برای نشان دادن live نمایش دهید
                    # partial = json.loads(rec.PartialResult()).get("partial", "")
                    # if partial and verbose:
                    #     print("partial:", partial, end="\r")
                    pass

    except KeyboardInterrupt:
        if verbose:
            print("\nInterrupted by user")

    # بعد از پایان، نتیجه‌ی نهایی را بگیریم
    try:
        final = json.loads(rec.FinalResult()).get("text", "")
        if final:
            text_parts.append(final)
    except Exception:
        pass

    full_text = " ".join(p for p in text_parts if p).strip()
    return full_text

def main():
    parser = argparse.ArgumentParser(description="Offline microphone -> text (VOSK)")
    parser.add_argument("--model", "-m", required=False, help="Path to VOSK model directory (e.g. ./model)", default="./model")
    parser.add_argument("--timeout", "-t", type=float, default=None,
                        help="Max seconds to listen (default: None, until Ctrl+C)")
    args = parser.parse_args()

    try:
        result = transcribe_from_mic(args.model, timeout=args.timeout, verbose=True)
        print("\n=== Final recognized text ===")
        print(result)
    except Exception as e:
        print("Error:", e, file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
