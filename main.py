# This Python file uses the following encoding: utf-8
import sys
import os
import socket
import struct
import json
import threading
import time

os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = './platforms'

from PySide2.QtWidgets import QApplication, QWidget
from PySide2.QtCore import QFile, Signal
from PySide2.QtUiTools import QUiLoader

socket.setdefaulttimeout(10)
DEBUG = False
STORE_PATH = os.path.join(os.getcwd(), 'store')
close_command = False
upload_status = False
total = 0
progress = 0

class Main(QWidget):
    signal_thread_start = Signal(str)
    signal_progress = Signal(int)
    signal_upload_status = Signal(str)
    signal_history = Signal(str)
    signal_single_upload = Signal(str)
    def __init__(self):
        super(Main, self).__init__()
        self.load_ui()
        res = os.path.exists(STORE_PATH)
        if not res:
            os.makedirs(STORE_PATH)

    def __del__(self):
        global close_command
        close_command = True

    def load_ui(self):
        loader = QUiLoader()
        path = "./form.ui"
        ui_file = QFile(path)
        ui_file.open(QFile.ReadOnly)
        self.ui = loader.load(ui_file, self)
        ui_file.close()
        self.ip = str(socket.gethostbyname(socket.gethostname()))
        self.ui.ipBox.setText(self.ip)


    def widget_setting(self):
        self.ui.startServerButton.clicked.connect(self.start_server_thread)
        self.ui.closeServerButton.clicked.connect(self.stop_server)
        self.ui.openFileManagerButton.clicked.connect(self.open_store)
        self.signal_thread_start.connect(self.update_status)
        self.signal_progress.connect(self.set_progress)
        self.signal_upload_status.connect(self.update_upload_status)
        self.signal_history.connect(self.update_history)
        self.signal_single_upload.connect(self.update_single_upload)

    def update_single_upload(self, string):
        self.ui.uploadProgressLabel.setText(string)

    def get_localtime(self):
        return str(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))

    def update_history(self, string):
        self.ui.historyBox.insertPlainText(string)

    def update_upload_status(self, string):
        self.ui.uploadStatusLabel.setText(string)

    def open_store(self):
        res = os.path.exists(STORE_PATH)
        if not res:
            os.makedirs(STORE_PATH)
        os.startfile(STORE_PATH)

    def set_progress(self, value):
        self.ui.progressBar.setValue(value)

    def update_status(self, string):
        self.ui.label_2.setText(string)

    def stop_server(self):
        global close_command
        close_command = True
        self.signal_thread_start.emit('关闭中...请等待10秒')
        self.ui.startServerButton.setEnabled(True)


    def start_server_thread(self):
        thread = threading.Thread(target=self.server_thread)
        thread.start()
        self.ui.startServerButton.setEnabled(False)

    def server_thread(self):
        global upload_status, total, progress
        sk = socket.socket()
        sk.bind((self.ip, 60000))  # 绑定ip地址和端口
        sk.listen()  # 开启监听
        self.signal_thread_start.emit("开启")
        print("服务端开启")
        buffer = 1024  # 缓冲区大小，这里好像因为windows的系统的原因，这个接收的缓冲区不能太大
        while True:
            try:
                if close_command:
                    break
                conn, addr = sk.accept()
                while True:
                    try:
                        if close_command:
                            break
                        # 先接收报头的长度
                        head_len = conn.recv(4)
                        head_len = struct.unpack('i', head_len)[0]  # 将报头长度解包出来
                        # 再接收报头
                        try:
                            json_head = conn.recv(head_len).decode('utf-8')
                            head = json.loads(json_head)  # 拿到原本的报头
                        except:
                            break
                        print(head)
                        if not upload_status:
                            upload_status = True
                            total = int(head['l'])
                            self.signal_upload_status.emit("是")
                            localtime = self.get_localtime()
                            content = localtime + ' 上传文件' + str(total) + '个\n'
                            self.signal_history.emit(content)
                        file_size = head['filesize']
                        save_path = os.path.join(STORE_PATH, head['filepath'])
                        print(save_path)
                        if not os.path.exists(save_path):
                            os.makedirs(save_path)
                        save_file_path = os.path.join(save_path, head['filename'])
                        # print(save_file_path)
                        if os.path.exists(save_file_path):
                            os.remove(save_file_path)
                        with open(save_file_path, 'ab') as f:
                            localtime = self.get_localtime()
                            content = localtime + " 开始传输文件" + save_file_path + '\n'
                            progress_str = str(file_size) + '/0'
                            self.signal_single_upload.emit(progress_str)
                            self.signal_history.emit(content)
                            current_file_size = 0
                            rec_status = {"status": 0}
                            while file_size:
                                if file_size >= buffer:  # 判断剩余文件的大小是否超过buffer
                                    content = conn.recv(buffer)
                                    f.write(content)
                                    file_size -= buffer
                                    current_file_size += buffer
                                    self.signal_single_upload.emit(str(head['filesize']) + '/' + str(current_file_size))
                                else:
                                    content = conn.recv(file_size)
                                    f.write(content)
                                    f.close()
                                    size = os.path.getsize(save_file_path)
                                    # current_file_size = 0
                                    self.signal_single_upload.emit(str(head['filesize']) + '/' + str(head['filesize']))
                                    if int(size) == int(head['filesize']):
                                        self.signal_history.emit(save_file_path + " 文件完整度检验正确\n")
                                    else:
                                        self.signal_history.emit(save_file_path + " 文件完整度检验错误！！！！\n")
                                        print("实际长度:", size, ",真实长度:", head['filesize'])
                                        rec_status['status'] = 1
                                    break
                            ready_content = str(rec_status['status'])
                            ready_content = ready_content.encode('utf-8')
                            conn.sendall(ready_content)

                        if upload_status:
                            progress += 1
                            value = int(progress/total * 100)
                            self.signal_progress.emit(value)
                            if progress == total:
                                upload_status = False
                                self.signal_progress.emit(0)
                                self.signal_single_upload.emit('0/0')
                                progress = 0
                                total = 0
                                self.signal_upload_status.emit("否")
                                localtime = self.get_localtime()
                                content = localtime + ' 上传文件完成\n'
                                self.signal_history.emit(content)
                        # conn.close()
                    except Exception:
                        if DEBUG:
                            import traceback
                            traceback.print_exc()
                        # print('close')
                        conn.close()
                        self.signal_progress.emit(0)
                        self.signal_single_upload.emit('0/0')
                        break
            except Exception:
                if DEBUG:
                    import traceback
                    traceback.print_exc()
                self.signal_progress.emit(0)
                self.signal_single_upload.emit('0/0')
                continue
        sk.close()
        self.signal_thread_start.emit("关闭")
        print("服务端线程结束")


if __name__ == "__main__":
    app = QApplication([])
    widget = Main()
    widget.setWindowTitle("采集文件上传服务端")
    widget.widget_setting()
    widget.show()
    sys.exit(app.exec_())
