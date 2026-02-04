import tkinter as tk
from tkinter import ttk, scrolledtext
import serial, serial.tools.list_ports
import requests, io, time, struct, threading
from PIL import Image

class VietQRApp:
    def __init__(self, root):
        self.root = root
        self.root.title("QR Scan Manager")
        self.root.geometry("500x450")
        self.ser = None
        self.is_running = False
        self.last_stt = -1
        self.session = requests.Session()
        self.script_url = "https://script.google.com/macros/s/AKfycbyFtQRn8BBO6KmzwLMnJxkePC4WaKsIAT9h-UoruDD6J0CZhJTWEdxYgPxeSMZ8o-5Lhw/exec"

        frame_top = ttk.Frame(root, padding=10)
        frame_top.pack(fill=tk.X)
        ttk.Label(frame_top, text="Cổng COM:").pack(side=tk.LEFT)
        self.cb_ports = ttk.Combobox(frame_top, values=[p.device for p in serial.tools.list_ports.comports()])
        self.cb_ports.pack(side=tk.LEFT, padx=5)
        self.btn_connect = ttk.Button(frame_top, text="Kết nối", command=self.toggle_connection)
        self.btn_connect.pack(side=tk.LEFT)
        self.log_area = scrolledtext.ScrolledText(root, height=15, state='disabled')
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.auto_detect_port()

    def auto_detect_port(self):
        for p in serial.tools.list_ports.comports():
            if any(x in p.device.lower() for x in ["usb", "ch340", "cp210"]):
                self.cb_ports.set(p.device); break

    def log(self, msg):
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {msg}\n")
        self.log_area.see(tk.END); self.log_area.config(state='disabled')

    def toggle_connection(self):
        if not self.ser:
            try:
                self.ser = serial.Serial(self.cb_ports.get(), 460800, timeout=1)
                self.btn_connect.config(text="Ngắt kết nối"); self.is_running = True
                self.log(f"Đã kết nối {self.cb_ports.get()}")
                threading.Thread(target=self.monitor_thread, daemon=True).start()
            except Exception as e: self.log(f"Lỗi: {e}")
        else:
            self.is_running = False; time.sleep(0.5)
            if self.ser: self.ser.close()
            self.ser = None; self.btn_connect.config(text="Kết nối")

    def monitor_thread(self):
        while self.is_running:
            try:
                data = self.session.get(self.script_url, timeout=3).json()
                if data.get("status") == "ok" and data.get("stt") != self.last_stt:
                    if self.last_stt != -1:
                        self.log(f"Đơn mới: {data['ten']} - {data['sotien']}đ")
                        self.send_to_esp(data['sotien'], data['ten'])
                    self.last_stt = data.get("stt")
            except: pass
            time.sleep(0.5)

    def send_to_esp(self, sotien, ten):
        amt = sotien.replace('.', '').replace(',', '')
        url = f"https://img.vietqr.io/image/970437-045704070016757-qr_only.png?amount={amt}&addInfo={ten.replace(' ','%20')}%20CK%20TIEN%20THUOC%20CS1&accountName=BENH%20VIEN%20DA%20KHOA%20BUU%20DIEN"
        
        try:
            img_data = self.session.get(url).content
            img = Image.open(io.BytesIO(img_data)).convert('RGB')
            
            # 1. Scale nhỏ lại còn 180x180 để không bị cắt
            QR_SIZE = 180 
            img = img.resize((QR_SIZE, QR_SIZE), Image.Resampling.LANCZOS)
            
            raw = bytearray()
            for y in range(QR_SIZE):
                for x in range(QR_SIZE):
                    r, g, b = img.getpixel((x, y))
                    rgb = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
                    raw.extend(struct.pack('>H', rgb))
            
            if self.ser and self.ser.is_open:
                self.ser.write(b'\xAA')
                self.ser.write(f"{ten}\n".encode('utf-8'))
                self.ser.write(f"{sotien}\n".encode('utf-8'))
                time.sleep(0.2) 
                
                # Gửi theo đúng kích thước mới
                chunk_size = QR_SIZE * 2 # Gửi từng dòng một cho an toàn
                for i in range(0, len(raw), chunk_size):
                    self.ser.write(raw[i : i + chunk_size])
                    time.sleep(0.002) # Delay nhẹ để ESP32 kịp vẽ
                    
                threading.Timer(30, lambda: self.ser.write(b'\xFF') if self.ser else None).start()
        except Exception as e:
            self.log(f"Lỗi: {e}")

if __name__ == "__main__":
    root = tk.Tk(); app = VietQRApp(root); root.mainloop()