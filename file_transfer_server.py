import socket
import threading
from flask import Flask, jsonify, request, render_template
import os
import uuid  # Thêm thư viện để tạo ID duy nhất
import json  # Thêm thư viện để xử lý file JSON
from datetime import datetime  # Thêm thư viện để xử lý thời gian
import base64  # Thêm thư viện để xử lý Base64

# Đảm bảo Flask tìm đúng thư mục templates
template_dir = os.path.join(os.path.dirname(__file__), 'templates')
app = Flask(__name__, template_folder=template_dir)

clients = {}  # Lưu trữ ID và socket của các thiết bị
messages = []  # Lưu trữ danh sách tin nhắn
MESSAGE_HISTORY_FILE = os.path.join(os.path.dirname(__file__), 'message_history.json')
DEVICE_ID_FILE = os.path.join(os.path.dirname(__file__), 'device_ids.json')
DATAFILE_DIR = os.path.join(os.path.dirname(__file__), 'datafile')
os.makedirs(DATAFILE_DIR, exist_ok=True)  # Tạo thư mục 'datafile' nếu chưa tồn tại

def load_message_history():
    """Tải lịch sử tin nhắn từ file JSON."""
    if os.path.exists(MESSAGE_HISTORY_FILE):
        with open(MESSAGE_HISTORY_FILE, 'r') as file:
            content = file.read().strip()
            return json.loads(content) if content else []  # Trả về danh sách trống nếu file rỗng
    return []  # Trả về danh sách trống nếu file không tồn tại

def load_device_ids():
    """Tải danh sách ID thiết bị từ file JSON."""
    if os.path.exists(DEVICE_ID_FILE):
        with open(DEVICE_ID_FILE, 'r') as file:
            content = file.read().strip()
            return json.loads(content) if content else {}  # Trả về dict trống nếu file rỗng
    return {}  # Trả về dict trống nếu file không tồn tại

def save_message_history():
    """Lưu lịch sử tin nhắn vào file JSON."""
    with open(MESSAGE_HISTORY_FILE, 'w') as file:
        json.dump(messages, file, indent=4)

def save_device_ids(device_ids):
    """Lưu danh sách ID thiết bị vào file JSON."""
    with open(DEVICE_ID_FILE, 'w') as file:
        json.dump(device_ids, file, indent=4)

# Tải lịch sử tin nhắn khi khởi động server
messages = load_message_history()

# Tải danh sách ID thiết bị khi khởi động server
device_ids = load_device_ids()

@app.route('/')
def index():
    """Trang chính hiển thị giao diện người dùng."""
    return render_template('index.html')

@app.route('/devices', methods=['GET'])
def list_devices():
    """API để liệt kê các thiết bị đã kết nối."""
    return jsonify(list(clients.keys()))

@app.route('/send_request', methods=['POST'])
def send_request():
    """API để gửi yêu cầu kết nối từ một thiết bị đến thiết bị khác."""
    data = request.json
    sender_id = data.get('sender_id')
    target_id = data.get('target_id')
    if target_id in clients:
        target_socket = clients[target_id]
        target_socket.send(f"REQUEST|{sender_id}".encode())
        return jsonify({"status": "Request sent"})
    return jsonify({"status": "Target not found"}), 404

@app.route('/send_file', methods=['POST'])
def send_file():
    """API để nhận và lưu trữ hình ảnh dưới dạng Base64."""
    data = request.json
    sender_id = data.get('sender_id')
    file_name = data.get('file_name')  # Tên file
    file_data = data.get('file_data')  # Nội dung file được mã hóa Base64
    if sender_id and file_name and file_data:
        try:
            # Lưu thông tin hình ảnh vào danh sách tin nhắn
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_message = {
                'sender_id': sender_id,
                'file_name': file_name,
                'file_data': file_data,
                'timestamp': timestamp
            }
            messages.append(new_message)
            save_message_history()  # Lưu vào file JSON
            return jsonify({"status": "Image saved as Base64"})
        except Exception as e:
            print(f"Error saving image: {e}")
            return jsonify({"status": f"Error: {str(e)}"}), 500
    return jsonify({"status": "Invalid data"}), 400

@app.route('/messages', methods=['GET'])
def get_messages():
    """API để lấy danh sách tin nhắn."""
    global messages
    # Tự động tải lại tin nhắn nếu file JSON bị xóa
    messages = load_message_history()
    # Chỉ trả về tối đa 50 tin nhắn gần nhất
    return jsonify(messages[-50:])

@app.route('/send_message', methods=['POST'])
def send_message():
    """API để nhận và phát tin nhắn."""
    data = request.json
    sender_id = data.get('sender_id')
    message = data.get('message')
    if sender_id and message:
        # Lưu tin nhắn với thời gian
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_message = {'sender_id': sender_id, 'message': message, 'timestamp': timestamp}
        messages.append(new_message)
        save_message_history()  # Lưu vào file JSON
        return jsonify({"status": "Message sent"})
    return jsonify({"status": "Invalid data"}), 400

@app.route('/send_image', methods=['POST'])
def send_image():
    """API để nhận và lưu trữ hình ảnh dưới dạng Base64."""
    data = request.json
    sender_id = data.get('sender_id')
    image_data = data.get('image_data')  # Hình ảnh được mã hóa Base64
    if sender_id and image_data:
        try:
            # Lưu hình ảnh với thời gian
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            new_message = {
                'sender_id': sender_id,
                'image_data': image_data,
                'timestamp': timestamp
            }
            messages.append(new_message)
            save_message_history()  # Lưu vào file JSON
            return jsonify({"status": "Image sent"})
        except Exception as e:
            print(f"Error saving image: {e}")
            return jsonify({"status": f"Error: {str(e)}"}), 500
    return jsonify({"status": "Invalid data"}), 400

def get_or_create_device_id(client_address):
    """Lấy ID của thiết bị dựa trên địa chỉ IP, hoặc tạo mới nếu chưa tồn tại."""
    ip_address = client_address[0]
    if ip_address not in device_ids:
        device_ids[ip_address] = str(uuid.uuid4())  # Tạo ID mới
        save_device_ids(device_ids)  # Lưu lại danh sách ID
    return device_ids[ip_address]

def handle_client(client_socket, client_address):
    """Xử lý kết nối từ client."""
    try:
        # Lấy hoặc tạo ID cho client
        client_id = get_or_create_device_id(client_address)
        clients[client_id] = client_socket
        print(f"Device {client_id} connected from {client_address}")

        # Gửi ID cho client
        client_socket.send(f"ID|{client_id}".encode())

        while True:
            # Nhận yêu cầu từ client
            data = client_socket.recv(1024).decode()
            if not data:
                break

            # Không cần xử lý CONNECT/CONFIRM/DENY nữa
            # Vì giờ chỉ tập trung vào khung tin nhắn
    except Exception as e:
        print(f"Error with client {client_address}: {e}")
    finally:
        # Xóa client khi ngắt kết nối
        if client_id in clients:
            del clients[client_id]
        client_socket.close()

def start_server(host='0.0.0.0', port=None):
    if port is None:
        port = int(os.environ.get("PORT", 5001))  # Lấy port từ biến môi trường
    app.run(host=host, port=port)
    
    """Khởi động server và giao diện web."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # Cho phép tái sử dụng cổng
    server.bind((host, port))  # Sửa lỗi cú pháp
    server.listen(5)
    print(f"Server started on {host}:{port}")

    # Chạy Flask trên một luồng riêng
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8001, debug=False)).start()  # Đổi cổng Flask từ 8000 sang 8001

    while True:
        client_socket, client_address = server.accept()
        threading.Thread(target=handle_client, args=(client_socket, client_address)).start()

if __name__ == "__main__":
    start_server()
