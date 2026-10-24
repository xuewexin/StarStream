#!/usr/bin/env python3
"""
CatCatch & M3U8 Sniffer Native Messaging Host
Chrome Native Messaging 协议: stdin/stdout JSON, 4-byte length prefix
支持与本地灵猫桌面客户端 (127.0.0.1:18910) 联动，支持唤醒及独立下载
"""
import sys
import os
import json
import struct
import subprocess
import urllib.request
import platform

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))

LOCAL_API_URL = "http://127.0.0.1:18910/api/tasks"

DEFAULT_CONFIG = {
    'exe_re': os.path.join(PROJECT_DIR, 'N_m3u8DL-RE.exe'),
    'exe_v3': os.path.join(PROJECT_DIR, 'N_m3u8DL-CLI_v3.0.2.exe'),
    'ffmpeg': os.path.join(PROJECT_DIR, 'ffmpeg.exe'),
    'save_dir': os.path.join(PROJECT_DIR, 'Downloads'),
    'proxy': '',
    'thread_count': 16,
    'del_after_done': True,
}


def read_message():
    raw_len = sys.stdin.buffer.read(4)
    if len(raw_len) < 4:
        return None
    msg_len = struct.unpack('@I', raw_len)[0]
    if msg_len == 0:
        return None
    msg_data = sys.stdin.buffer.read(msg_len)
    if not msg_data:
        return None
    return json.loads(msg_data.decode('utf-8'))


def send_message(msg):
    data = json.dumps(msg, ensure_ascii=False).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('@I', len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def forward_to_desktop_server(task_data):
    """尝试将任务直接转发给本地桌面应用程序 (绕过系统代理直接连接 127.0.0.1)"""
    try:
        req_data = json.dumps(task_data).encode('utf-8')
        req = urllib.request.Request(
            LOCAL_API_URL,
            data=req_data,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(req, timeout=1.5) as resp:
            if resp.status == 200:
                return True, json.loads(resp.read().decode('utf-8'))
    except Exception:
        pass
    return False, None


def launch_fallback_cli(data):
    """当桌面应用未在后台时，直接启动 N_m3u8DL 下载"""
    version = data.get('version', 'RE')
    exe = DEFAULT_CONFIG['exe_v3'] if version == 'V3' else DEFAULT_CONFIG['exe_re']

    if not os.path.exists(exe):
        return False, f"未找到可执行文件: {exe}"

    url = data['url']
    save_dir = data.get('saveDir') or DEFAULT_CONFIG['save_dir']
    save_name = data.get('saveName') or 'video'
    os.makedirs(save_dir, exist_ok=True)

    if version == 'RE':
        cmd = [exe, url, '--save-dir', save_dir, '--save-name', save_name]
        if os.path.exists(DEFAULT_CONFIG['ffmpeg']):
            cmd.extend(['--ffmpeg-binary-path', DEFAULT_CONFIG['ffmpeg']])
        thread_count = str(data.get('threadCount') or DEFAULT_CONFIG['thread_count'])
        cmd.extend(['--thread-count', thread_count])
        if data.get('delAfterDone', True):
            cmd.append('--auto-select')
    else:
        cmd = [exe, url, '--workDir', save_dir, '--saveName', save_name]
        if data.get('delAfterDone', True):
            cmd.append('--enableDelAfterDone')

    headers = data.get('headers', {})
    for k, v in headers.items():
        if v:
            cmd.extend(['-H', f'{k}: {v}'])

    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_DIR,
        creationflags=subprocess.CREATE_NEW_CONSOLE if platform.system() == 'Windows' else 0
    )
    return True, f"已在独立控制台启动下载 (PID: {proc.pid})"


def main():
    while True:
        msg = read_message()
        if msg is None:
            break

        try:
            # 兼容两种格式：{ action: 'download', data: {...} } 或直接传递 task 属性
            task_data = msg.get('data') if 'data' in msg else msg
            if not task_data or not task_data.get('url'):
                send_message({'success': False, 'message': 'Missing url field'})
                continue

            # 1. 优先发送给本地灵猫桌面客户端
            forwarded, resp = forward_to_desktop_server(task_data)
            if forwarded:
                send_message({
                    'success': True,
                    'message': '任务已成功推送到灵猫桌面客户端',
                    'client_response': resp
                })
                continue

            # 2. 客户端未运行，回退到直接启动 CLI 下载
            ok, message = launch_fallback_cli(task_data)
            send_message({'success': ok, 'message': message})

        except Exception as e:
            send_message({'success': False, 'message': str(e)})


if __name__ == '__main__':
    main()
