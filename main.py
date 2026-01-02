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
    def __init__(self, root):
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-transparentcolor", "systemTransparent") # Hỗ trợ nền trong suốt nếu cần
        self.win.config(bg="systemTransparent")
        
        # Biến trạng thái
        self.full_text = ""
        self.is_loading = False
        self.blink_state = True

        # Kích thước
        self.dot_size = 20
        self.expanded_width = 300

        # UI: Chấm nhỏ
        self.canvas = tk.Canvas(self.win, width=self.dot_size, height=self.dot_size, 
                               bg="systemTransparent", highlightthickness=0)
        self.dot = self.canvas.create_oval(2, 2, self.dot_size-2, self.dot_size-2, fill="orange", outline="")
        self.canvas.pack(side="right")

        # UI: Nhãn câu trả lời (ẩn lúc đầu)
        self.label = tk.Label(self.win, text="", bg="#2c3e50", fg="white", 
                              padx=10, pady=10, font=("Arial", 10), wraplength=250, justify="left")
        
        # Vị trí góc dưới bên phải
        self.screen_w = self.win.winfo_screenwidth()
        self.screen_h = self.win.winfo_screenheight()
        self.update_position(expanded=False)

        # Sự kiện
        self.win.bind("<Enter>", self.expand)
        self.win.bind("<Leave>", self.collapse)
        
        self.win.withdraw() # Ẩn lúc khởi tạo

    def update_position(self, expanded=False):
        self.win.update_idletasks()
        w = self.win.winfo_width()
        h = self.win.winfo_height()
        # Đặt ở góc dưới bên phải, cách lề 20px
        self.win.geometry(f"+{self.screen_w - w - 20}+{self.screen_h - h - 60}")

    def start_loading(self):
        self.is_loading = True
        self.full_text = "Đang xử lý..."
        self.canvas.itemconfig(self.dot, fill="orange")
        self.win.deiconify()
        self.blink()

    def blink(self):
        if self.is_loading:
            color = "orange" if self.blink_state else "#553300"
            self.canvas.itemconfig(self.dot, fill=color)
            self.blink_state = not self.blink_state
            self.win.after(500, self.blink)

    def set_answer(self, text):
        self.is_loading = False
        self.full_text = text
        self.canvas.itemconfig(self.dot, fill="#2ecc71") # Xanh lá
        self.label.config(text=f"Gemini: {text}")
        # Tự động biến mất sau 15 giây nếu không tương tác
        self.win.after(15000, self.win.withdraw)

    def expand(self, event=None):
        if not self.is_loading:
            self.label.pack(side="left", fill="both", expand=True)
            self.update_position(expanded=True)
            self.win.attributes("-alpha", 1.0)

    def collapse(self, event=None):
        self.label.pack_forget()
        self.update_position(expanded=False)
        self.win.attributes("-alpha", 0.7)

class WifiSwitcherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("WiFi Gemini Assistant")
        self.root.geometry("350x450")
        
        self.wifi1_ssid = tk.StringVar(value="WIFI_NHA_1")
        self.wifi2_ssid = tk.StringVar(value="WIFI_DUNG_API")
        self.hotkey_trigger = tk.StringVar(value="ctrl+f8")

        self.overlay = OverlayAnswer(self.root) # Tạo overlay dùng chung
        self.setup_ui()
        self.root.protocol('WM_DELETE_WINDOW', self.hide_window)

    def setup_ui(self):
        tk.Label(self.root, text="WiFi 1 (Chính):", font=('Arial', 10, 'bold')).pack(pady=5)
        tk.Entry(self.root, textvariable=self.wifi1_ssid, width=30).pack()

        tk.Label(self.root, text="WiFi 2 (Để gọi API):", font=('Arial', 10, 'bold')).pack(pady=5)
        tk.Entry(self.root, textvariable=self.wifi2_ssid, width=30).pack()

        tk.Label(self.root, text="Phím tắt kích hoạt:").pack(pady=5)
        tk.Entry(self.root, textvariable=self.hotkey_trigger, width=15).pack()

        tk.Button(self.root, text="Lưu & Kích hoạt", command=self.start_listening, bg="#27ae60", fg="white", height=2).pack(pady=20)

    def connect_wifi(self, ssid):
        try:
            subprocess.run(f'netsh wlan connect name="{ssid}"', shell=True, capture_output=True)
            time.sleep(3) 
            return True
        except Exception as e:
            print(f"Lỗi kết nối WiFi: {e}")
            return False

    def is_connected(self):
        try:
            subprocess.check_call(["ping", "-n", "1", "8.8.8.8"], stdout=subprocess.DEVNULL, timeout=2)
            return True
        except:
            return False

    def process_gemini_workflow(self):
        try:
            # Hiển thị overlay trạng thái loading ngay lập tức
            self.root.after(0, self.overlay.start_loading)
            
            print("Đang chuyển mạng...")
            self.connect_wifi(self.wifi2_ssid.get())
            
            retries = 0
            while not self.is_connected() and retries < 5:
                time.sleep(2)
                retries += 1

            answer = "Không tìm thấy nội dung để hỏi."
            client = get_gemini_client()
            prompt = "Trả lời thật ngắn gọn chỉ có tên đáp án và nội dung đáp án đó (VD: A.12):"

            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                response = client.models.generate_content(
                    model="gemini-2.0-flash", 
                    contents=[prompt, types.Part.from_bytes(data=img_byte_arr.getvalue(), mime_type='image/png')]
                )
                answer = response.text
            else:
                text_content = clipboard.paste()
                if text_content:
                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=f"{prompt} {text_content}"
                    )
                    answer = response.text

            # Chuyển về WiFi 1
            print(f"Kết quả: {answer}. Đang quay về WiFi chính...")
            self.connect_wifi(self.wifi1_ssid.get())

            # Cập nhật kết quả lên Overlay
            self.root.after(0, lambda: self.overlay.set_answer(answer))

        except Exception as e:
            print(f"Lỗi: {e}")
            self.connect_wifi(self.wifi1_ssid.get())
            self.root.after(0, lambda: self.overlay.set_answer(f"Lỗi: {str(e)}"))

    def start_listening(self):
        try:
            keyboard.unhook_all()
            keyboard.add_hotkey(self.hotkey_trigger.get(), 
                                lambda: threading.Thread(target=self.process_gemini_workflow, daemon=True).start())
            messagebox.showinfo("Thông báo", f"Đã kích hoạt! Nhấn {self.hotkey_trigger.get()} khi cần.")
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
        image = Image.new('RGB', (64, 64), (46, 204, 113))
        dc = ImageDraw.Draw(image)
        dc.ellipse((10, 10, 54, 54), fill=(255, 255, 255))
        menu = pystray.Menu(pystray.MenuItem('Cài đặt', self.show_window), pystray.MenuItem('Thoát', self.quit_app))
        self.icon = pystray.Icon("WifiGemini", image, "WiFi Gemini Assistant", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = WifiSwitcherApp(root)
    root.mainloop()