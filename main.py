import tkinter as tk
from tkinter import messagebox
import keyboard
import subprocess
import threading
import pystray
from PIL import Image, ImageDraw
import sys
import os

class WifiSwitcherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("WiFi Switcher")
        self.root.geometry("350x400")
        
        # Biến lưu trữ thông tin
        self.wifi1_ssid = tk.StringVar()
        self.wifi2_ssid = tk.StringVar()
        self.hotkey1 = tk.StringVar(value="f9")
        self.hotkey2 = tk.StringVar(value="f10")

        self.setup_ui()
        
        # Giao diện sẽ ẩn khi đóng thay vì thoát hẳn
        self.root.protocol('WM_DELETE_WINDOW', self.hide_window)

    def setup_ui(self):
        # Frame WiFi 1
        tk.Label(self.root, text="WiFi 1 (SSID):", font=('Arial', 10, 'bold')).pack(pady=5)
        tk.Entry(self.root, textvariable=self.wifi1_ssid, width=30).pack()
        tk.Label(self.root, text="Phím tắt WiFi 1 (VD: f9):").pack()
        tk.Entry(self.root, textvariable=self.hotkey1, width=10).pack()

        tk.Label(self.root, text="-"*40).pack(pady=10)

        # Frame WiFi 2
        tk.Label(self.root, text="WiFi 2 (SSID):", font=('Arial', 10, 'bold')).pack(pady=5)
        tk.Entry(self.root, textvariable=self.wifi2_ssid, width=30).pack()
        tk.Label(self.root, text="Phím tắt WiFi 2 (VD: f10):").pack()
        tk.Entry(self.root, textvariable=self.hotkey2, width=10).pack()

        # Nút điều khiển
        tk.Button(self.root, text="Lưu & Kích hoạt phím tắt", command=self.start_listening, bg="green", fg="white").pack(pady=20)
        tk.Label(self.root, text="Ứng dụng sẽ chạy ngầm dưới khay hệ thống", font=('Arial', 8, 'italic')).pack()

    def connect_wifi(self, ssid):
        """Hàm thực hiện kết nối WiFi bằng lệnh netsh"""
        try:
            print(f"Đang kết nối tới: {ssid}...")
            # Lưu ý: Profile WiFi phải đã tồn tại trên máy (đã từng đăng nhập trước đó)
            result = subprocess.run(f'netsh wlan connect name="{ssid}"', capture_output=True, text=True, shell=True)
            if "thành công" in result.stdout or "successfully" in result.stdout.lower():
                print(f"Đã chuyển sang {ssid}")
            else:
                print(f"Lỗi: {result.stdout}")
        except Exception as e:
            print(f"Lỗi thực thi: {e}")

    def start_listening(self):
        """Đăng ký phím tắt"""
        try:
            # Xóa các hotkey cũ nếu có
            keyboard.unhook_all()
            
            # Đăng ký hotkey mới
            keyboard.add_hotkey(self.hotkey1.get(), lambda: self.connect_wifi(self.wifi1_ssid.get()))
            keyboard.add_hotkey(self.hotkey2.get(), lambda: self.connect_wifi(self.wifi2_ssid.get()))
            
            messagebox.showinfo("Thông báo", "Đã kích hoạt phím tắt thành công!")
            self.hide_window()
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể thiết lập phím tắt: {e}")

    def hide_window(self):
        self.root.withdraw() # Ẩn cửa sổ
        self.create_tray_icon()

    def show_window(self, icon, item):
        icon.stop() # Dừng tray icon
        self.root.after(0, self.root.deiconify) # Hiện lại cửa sổ

    def quit_app(self, icon, item):
        icon.stop()
        self.root.quit()
        sys.exit()

    def create_tray_icon(self):
        # Tạo icon đơn giản bằng Pillow
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), (255, 255, 255))
        dc = ImageDraw.Draw(image)
        dc.rectangle((width // 4, height // 4, width * 3 // 4, height * 3 // 4), fill=(0, 120, 215))

        menu = pystray.Menu(
            pystray.MenuItem('Hiện cài đặt', self.show_window),
            pystray.MenuItem('Thoát', self.quit_app)
        )
        
        self.icon = pystray.Icon("WifiSwitcher", image, "WiFi Switcher", menu)
        # Chạy tray icon trong một thread riêng để không treo UI
        threading.Thread(target=self.icon.run, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = WifiSwitcherApp(root)
    root.mainloop()