import tkinter as tk
from tkinter import messagebox
import keyboard
import subprocess
import threading
import pystray
from PIL import Image, ImageDraw, ImageGrab
import sys
import os
import time
import io
import clipboard
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv() 

def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:

        raise ValueError("GEMINI_API_KEY chưa được thiết lập.")
    return genai.Client(api_key=api_key)

class OverlayAnswer:
    def __init__(self, text):
        self.win = tk.Toplevel()
        self.win.overrideredirect(True)  
        self.win.attributes("-topmost", True)  
        self.win.attributes("-alpha", 0.3)  
        
        label_text = f"Gemini: {text}"
        self.label = tk.Label(self.win, text=label_text, bg="#2c3e50", fg="white", 
                              padx=10, pady=10, font=("Arial", 10), wraplength=250, justify="left")
        self.label.pack()

        self.close_btn = tk.Button(self.win, text="X", command=self.win.destroy, 
                                   bg="#e74c3c", fg="white", bd=0, font=("Arial", 7))
        self.close_btn.place(relx=1.0, rely=0.0, anchor="ne")

        screen_width = self.win.winfo_screenwidth()
        screen_height = self.win.winfo_screenheight()
        self.win.update_idletasks()
        width = self.win.winfo_width()
        height = self.win.winfo_height()
        self.win.geometry(f"{width}x{height}+{screen_width - width - 20}+{screen_height - height - 60}")

        self.win.bind("<Enter>", lambda e: self.win.attributes("-alpha", 1.0))
        self.win.bind("<Leave>", lambda e: self.win.attributes("-alpha", 0.3))
        self.win.after(10000, self.win.destroy)
        
class WifiSwitcherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("WiFi Gemini Assistant")
        self.root.geometry("350x450")
        
        self.wifi1_ssid = tk.StringVar(value="WIFI_NHA_1")
        self.wifi2_ssid = tk.StringVar(value="WIFI_DUNG_API")
        self.hotkey_trigger = tk.StringVar(value="ctrl+f8") # Phím tắt để bắt đầu quy trình

        self.setup_ui()
        self.root.protocol('WM_DELETE_WINDOW', self.hide_window)

    def setup_ui(self):
        tk.Label(self.root, text="WiFi 1 (Chính):", font=('Arial', 10, 'bold')).pack(pady=5)
        tk.Entry(self.root, textvariable=self.wifi1_ssid, width=30).pack()

        tk.Label(self.root, text="WiFi 2 (Để gọi API):", font=('Arial', 10, 'bold')).pack(pady=5)
        tk.Entry(self.root, textvariable=self.wifi2_ssid, width=30).pack()

        tk.Label(self.root, text="Phím tắt kích hoạt (VD: ctrl+f8):").pack(pady=5)
        tk.Entry(self.root, textvariable=self.hotkey_trigger, width=15).pack()

        tk.Button(self.root, text="Lưu & Kích hoạt", command=self.start_listening, bg="#27ae60", fg="white", height=2).pack(pady=20)
        tk.Label(self.root, text="Cách dùng: Nhấn phím tắt, máy sẽ đổi WiFi,\nhỏi Gemini từ Clipboard/Ảnh và đổi về.", font=('Arial', 8, 'italic')).pack()

    def connect_wifi(self, ssid):
        try:
            subprocess.run(f'netsh wlan connect name="{ssid}"', shell=True, capture_output=True)
            # Chờ một chút để kết nối ổn định
            time.sleep(3) 
            return True
        except Exception as e:
            print(f"Lỗi kết nối WiFi: {e}")
            return False

    def is_connected(self):
        """Kiểm tra xem có internet chưa"""
        try:
            # Ping thử tới Google DNS
            subprocess.check_call(["ping", "-n", "1", "8.8.8.8"], stdout=subprocess.DEVNULL, timeout=2)
            return True
        except:
            return False

    def process_gemini_workflow(self):
        """Quy trình chính: Đổi mạng -> Hỏi -> Đổi lại"""
        try:
            print("Bắt đầu quy trình...")
            self.connect_wifi(self.wifi2_ssid.get())
            
            retries = 0
            while not self.is_connected() and retries < 5:
                time.sleep(2)
                retries += 1

            answer = "Không có dữ liệu trong clipboard."
            client = get_gemini_client()
            prompt = "Trả lời thật ngắn gọn chỉ có tên đáp án và nội dung đáp án đó (VD: A.12):"

            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                # Xử lý ảnh
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                response = client.models.generate_content(
                    model="gemini-2.5-flash", # Cập nhật model mới nhất
                    contents=[prompt, types.Part.from_bytes(data=img_byte_arr.getvalue(), mime_type='image/png')]
                )
                answer = response.text
            else:
                # Xử lý text
                text_content = clipboard.paste()
                if text_content:
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=f"{prompt} {text_content}"
                    )
                    answer = response.text

            # 3. Chuyển về WiFi 1
            print(f"Kết quả: {answer}. Đang quay về WiFi chính...")
            self.connect_wifi(self.wifi1_ssid.get())

            # 4. Hiển thị Overlay (Phải chạy trong thread chính của Tkinter)
            self.root.after(0, lambda: OverlayAnswer(answer))

        except Exception as e:
            print(f"Lỗi quy trình: {e}")
            self.connect_wifi(self.wifi1_ssid.get()) # Trả về wifi 1 nếu lỗi

    def start_listening(self):
        try:
            keyboard.unhook_all()
            # Khi nhấn phím tắt, chạy quy trình trong thread mới để không treo app
            keyboard.add_hotkey(self.hotkey_trigger.get(), 
                                lambda: threading.Thread(target=self.process_gemini_workflow, daemon=True).start())
            
            messagebox.showinfo("Thông báo", f"Đã kích hoạt! Nhấn {self.hotkey_trigger.get()} để bắt đầu.")
            self.hide_window()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể thiết lập phím tắt: {e}")

    def hide_window(self):
        self.root.withdraw()
        self.create_tray_icon()

    def show_window(self, icon, item):
        icon.stop()
        self.root.after(0, self.root.deiconify)

    def quit_app(self, icon, item):
        icon.stop()
        self.root.quit()
        os._exit(0)

    def create_tray_icon(self):
        width, height = 64, 64
        image = Image.new('RGB', (width, height), (46, 204, 113))
        dc = ImageDraw.Draw(image)
        dc.ellipse((10, 10, 54, 54), fill=(255, 255, 255))

        menu = pystray.Menu(
            pystray.MenuItem('Hiện cài đặt', self.show_window),
            pystray.MenuItem('Thoát', self.quit_app)
        )
        self.icon = pystray.Icon("WifiGemini", image, "WiFi Gemini Assistant", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = WifiSwitcherApp(root)
    root.mainloop()