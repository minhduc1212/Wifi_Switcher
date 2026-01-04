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

# ============================================
# PHẦN TỰ ĐỘNG ẨN CONSOLE WINDOW
# ============================================
def hide_console():
    """Ẩn cửa sổ console trên Windows"""
    if sys.platform == "win32":
        try:
            import ctypes
            # Lấy handle của console window
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd != 0:
                # SW_HIDE = 0: Ẩn cửa sổ
                ctypes.windll.user32.ShowWindow(hwnd, 0)
                # Vô hiệu hóa nút Close
                ctypes.windll.user32.EnableMenuItem(
                    ctypes.windll.user32.GetSystemMenu(hwnd, False),
                    0xF060,  # SC_CLOSE
                    0x00000001  # MF_BYCOMMAND | MF_GRAYED
                )
        except Exception as e:
            print(f"Không thể ẩn console: {e}")

def restart_as_no_console():
    """Khởi động lại ứng dụng với pythonw.exe (không console)"""
    if sys.platform == "win32":
        # Kiểm tra xem đang chạy bằng python.exe hay pythonw.exe
        if "python.exe" in sys.executable.lower():
            pythonw = sys.executable.replace("python.exe", "pythonw.exe")
            
            if os.path.exists(pythonw):
                try:
                    # Khởi động lại với pythonw.exe
                    subprocess.Popen(
                        [pythonw] + sys.argv,
                        creationflags=subprocess.CREATE_NO_WINDOW | 
                                    subprocess.CREATE_NEW_PROCESS_GROUP | 
                                    subprocess.DETACHED_PROCESS,
                        cwd=os.getcwd(),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        stdin=subprocess.DEVNULL,
                        close_fds=True
                    )
                    # Thoát instance hiện tại
                    sys.exit(0)
                except Exception as e:
                    print(f"Không thể khởi động lại với pythonw: {e}")
                    # Nếu không thể khởi động lại, ẩn console hiện tại
                    hide_console()
            else:
                # Nếu không có pythonw.exe, chỉ ẩn console
                hide_console()

# Gọi hàm ẩn console ngay khi chương trình bắt đầu
restart_as_no_console()
# ============================================

load_dotenv() 

def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY chưa được thiết lập.")
    return genai.Client(api_key=api_key)

class StealthOverlay:
    def __init__(self, root):
        self.root = root
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.0)  # Bắt đầu trong suốt hoàn toàn
        
        # Trạng thái
        self.full_text = ""
        self.is_loading = False
        self.is_expanded = False
        self.auto_hide_timer = None
        
        # Kích thước nhỏ gọn
        self.collapsed_size = 8
        self.min_width = 60
        self.max_width = 200
        self.padding = 20
        
        # Container chính với bo góc
        self.container = tk.Frame(self.win, bg="#1a1a1a", highlightthickness=0)
        self.container.pack(fill="both", expand=True)
        
        # Indicator dot (trạng thái thu gọn)
        self.dot_canvas = tk.Canvas(self.container, width=self.collapsed_size, 
                                    height=self.collapsed_size, bg="#1a1a1a", 
                                    highlightthickness=0, bd=0)
        self.dot = self.dot_canvas.create_oval(1, 1, self.collapsed_size-1, 
                                               self.collapsed_size-1, 
                                               fill="#555555", outline="")
        self.dot_canvas.pack()
        
        # Panel mở rộng (ẩn ban đầu)
        self.expanded_frame = tk.Frame(self.container, bg="#1a1a1a")
        
        # Header nhỏ gọn
        self.header = tk.Frame(self.expanded_frame, bg="#2a2a2a", height=20)
        self.header.pack(fill="x")
        self.header.pack_propagate(False)
        
        self.status_label = tk.Label(self.header, text="●", bg="#2a2a2a", 
                                     fg="#888888", font=("Segoe UI", 8))
        self.status_label.pack(side="left", padx=5)
        
        # Nội dung câu trả lời
        self.answer_label = tk.Label(self.expanded_frame, text="", 
                                     bg="#1a1a1a", fg="#e0e0e0",
                                     font=("Segoe UI", 10, "bold"),
                                     justify="center", padx=8, pady=6)
        self.answer_label.pack()
        
        # Vị trí
        self.screen_w = self.win.winfo_screenwidth()
        self.screen_h = self.win.winfo_screenheight()
        self.position_window(collapsed=True)
        
        # Events
        self.win.bind("<Enter>", self.on_hover_enter)
        self.win.bind("<Leave>", self.on_hover_leave)
        
        self.win.withdraw()
        
    def position_window(self, collapsed=True):
        self.win.update_idletasks()
        
        if collapsed:
            w, h = self.collapsed_size, self.collapsed_size
            x = self.screen_w - w - 5
            y = self.screen_h - h - 50
        else:
            # Tính toán kích thước dựa trên nội dung
            w = self.answer_label.winfo_reqwidth() + self.padding
            h = self.answer_label.winfo_reqheight() + 20  # +20 cho header
            
            # Giới hạn kích thước
            w = max(self.min_width, min(w, self.max_width))
            
            x = self.screen_w - w - 10
            y = self.screen_h - h - 60
        
        self.win.geometry(f"{w}x{h}+{x}+{y}")
    
    def fade_in(self, target_alpha=0.95, step=0.1):
        current = self.win.attributes("-alpha")
        if current < target_alpha:
            self.win.attributes("-alpha", min(current + step, target_alpha))
            self.win.after(30, lambda: self.fade_in(target_alpha, step))
    
    def fade_out(self, callback=None):
        current = self.win.attributes("-alpha")
        if current > 0:
            self.win.attributes("-alpha", max(current - 0.15, 0))
            self.win.after(30, lambda: self.fade_out(callback))
        elif callback:
            callback()
    
    def start_loading(self):
        self.is_loading = True
        self.full_text = ""
        self.dot_canvas.itemconfig(self.dot, fill="#ff9500")
        self.win.deiconify()
        self.fade_in(target_alpha=0.7)
        self.animate_loading()
    
    def animate_loading(self):
        if self.is_loading:
            current_color = self.dot_canvas.itemcget(self.dot, "fill")
            new_color = "#ff9500" if current_color == "#ff6600" else "#ff6600"
            self.dot_canvas.itemconfig(self.dot, fill=new_color)
            self.win.after(400, self.animate_loading)
    
    def set_answer(self, text):
        self.is_loading = False
        self.full_text = text
        self.dot_canvas.itemconfig(self.dot, fill="#00ff88")
        self.answer_label.config(text=text)
        self.status_label.config(text="●", fg="#00ff88")
        
        # Tự động ẩn sau 12 giây
        if self.auto_hide_timer:
            self.win.after_cancel(self.auto_hide_timer)
        self.auto_hide_timer = self.win.after(12000, self.hide_overlay)
    
    def on_hover_enter(self, event=None):
        if not self.is_loading and self.full_text and not self.is_expanded:
            self.expand()
    
    def on_hover_leave(self, event=None):
        if self.is_expanded:
            self.collapse()
    
    def expand(self):
        self.is_expanded = True
        self.dot_canvas.pack_forget()
        self.expanded_frame.pack(fill="both", expand=True)
        self.position_window(collapsed=False)
        self.win.attributes("-alpha", 0.95)
    
    def collapse(self):
        self.is_expanded = False
        self.expanded_frame.pack_forget()
        self.dot_canvas.pack()
        self.position_window(collapsed=True)
        self.win.attributes("-alpha", 0.7)
    
    def hide_overlay(self):
        def after_fade():
            self.win.withdraw()
            self.collapse()
        self.fade_out(callback=after_fade)

class WifiSwitcherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("WiFi Gemini Assistant")
        self.root.geometry("380x480")
        self.root.configure(bg="#f5f5f5")
        
        self.wifi1_ssid = tk.StringVar(value="WIFI_NHA_1")
        self.wifi2_ssid = tk.StringVar(value="WIFI_DUNG_API")
        self.hotkey_trigger = tk.StringVar(value="ctrl+f8")

        self.overlay = StealthOverlay(self.root)
        self.setup_ui()
        self.root.protocol('WM_DELETE_WINDOW', self.hide_window)

    def setup_ui(self):
        # Header
        header = tk.Frame(self.root, bg="#2c3e50", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        tk.Label(header, text="WiFi Gemini Assistant", 
                bg="#2c3e50", fg="white", 
                font=("Segoe UI", 14, "bold")).pack(pady=15)
        
        # Main content
        content = tk.Frame(self.root, bg="#f5f5f5")
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # WiFi 1
        tk.Label(content, text="WiFi Chính:", bg="#f5f5f5", 
                font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
        entry1 = tk.Entry(content, textvariable=self.wifi1_ssid, 
                         font=("Segoe UI", 10), relief="solid", bd=1)
        entry1.pack(fill="x", pady=(0, 15))
        
        # WiFi 2
        tk.Label(content, text="WiFi API:", bg="#f5f5f5", 
                font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
        entry2 = tk.Entry(content, textvariable=self.wifi2_ssid, 
                         font=("Segoe UI", 10), relief="solid", bd=1)
        entry2.pack(fill="x", pady=(0, 15))
        
        # Hotkey
        tk.Label(content, text="Phím tắt:", bg="#f5f5f5", 
                font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 5))
        entry3 = tk.Entry(content, textvariable=self.hotkey_trigger, 
                         font=("Segoe UI", 10), relief="solid", bd=1, width=20)
        entry3.pack(anchor="w", pady=(0, 20))
        
        # Activate button
        btn = tk.Button(content, text="Kích hoạt", 
                       command=self.start_listening,
                       bg="#27ae60", fg="white", 
                       font=("Segoe UI", 11, "bold"),
                       relief="flat", cursor="hand2",
                       height=2)
        btn.pack(fill="x", pady=10)
        
        # Info
        info_text = "Overlay sẽ xuất hiện ở góc dưới phải màn hình\nDi chuột vào để xem đầy đủ câu trả lời"
        tk.Label(content, text=info_text, bg="#f5f5f5", 
                fg="#666666", font=("Segoe UI", 8),
                justify="center").pack(pady=(20, 0))

    def connect_wifi(self, ssid):
        try:
            subprocess.run(f'netsh wlan connect name="{ssid}"', 
                          shell=True, capture_output=True)
            time.sleep(3) 
            return True
        except Exception as e:
            print(f"Lỗi kết nối WiFi: {e}")
            return False

    def is_connected(self):
        try:
            subprocess.check_call(["ping", "-n", "1", "8.8.8.8"], 
                                stdout=subprocess.DEVNULL, timeout=2)
            return True
        except:
            return False

    def process_gemini_workflow(self):
        try:
            self.root.after(0, self.overlay.start_loading)
            
            print("Đang chuyển mạng...")
            self.connect_wifi(self.wifi2_ssid.get())
            
            retries = 0
            while not self.is_connected() and retries < 5:
                time.sleep(2)
                retries += 1

            answer = "Không tìm thấy nội dung"
            client = get_gemini_client()
            prompt = "Trả lời ngắn gọn chỉ đáp án (VD: A.12):"

            img = ImageGrab.grabclipboard()
            if isinstance(img, Image.Image):
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                response = client.models.generate_content(
                    model="gemini-2.5-flash", 
                    contents=[prompt, types.Part.from_bytes(
                        data=img_byte_arr.getvalue(), mime_type='image/png')]
                )
                answer = response.text
            else:
                text_content = clipboard.paste()
                if text_content:
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=f"{prompt} {text_content}"
                    )
                    answer = response.text

            print(f"Kết quả: {answer}")
            self.connect_wifi(self.wifi1_ssid.get())
            self.root.after(0, lambda: self.overlay.set_answer(answer))

        except Exception as e:
            print(f"Lỗi: {e}")
            self.connect_wifi(self.wifi1_ssid.get())
            self.root.after(0, lambda: self.overlay.set_answer(f"Lỗi: {str(e)}"))

    def start_listening(self):
        try:
            keyboard.unhook_all()
            keyboard.add_hotkey(
                self.hotkey_trigger.get(), 
                lambda: threading.Thread(
                    target=self.process_gemini_workflow, daemon=True).start()
            )
            messagebox.showinfo("Thành công", 
                              f"Đã kích hoạt!\nNhấn {self.hotkey_trigger.get()} để sử dụng")
            self.hide_window()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể thiết lập: {e}")

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
        menu = pystray.Menu(
            pystray.MenuItem('Cài đặt', self.show_window), 
            pystray.MenuItem('Thoát', self.quit_app)
        )
        self.icon = pystray.Icon("WifiGemini", image, 
                                "WiFi Gemini Assistant", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = WifiSwitcherApp(root)
    root.mainloop()