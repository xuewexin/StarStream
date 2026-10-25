"""
CatCatch Downloader - Error Logging & Diagnostic Engine
负责全系统运行日志持久化、失败任务根因智能诊断与错误报告导出
"""
import os
import sys
import time
import re
from .config import ROOT_DIR

LOGS_DIR = os.path.join(ROOT_DIR, "Logs")
MASTER_ERROR_LOG = os.path.join(LOGS_DIR, "download_errors.log")


def ensure_logs_dir():
    """确保 Logs 目录存在"""
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
    except Exception:
        pass
    return LOGS_DIR


def get_logs_dir():
    return ensure_logs_dir()


def get_master_error_log_path():
    ensure_logs_dir()
    return MASTER_ERROR_LOG


def diagnose_error(log_lines=None, error_msg="", url=""):
    """
    智能分析错误日志与异常信息，提炼人机可读的精准诊断原因与解决建议
    返回: (diagnostic_title, diagnostic_hint)
    """
    all_text = ""
    if log_lines:
        if isinstance(log_lines, list):
            all_text = "\n".join(str(l) for l in log_lines)
        else:
            all_text = str(log_lines)
    all_text += f"\n{error_msg}"

    # 0. 手动取消检测（最高优先级，避免将用户主动暂停误判为网络或服务端错误）
    if re.search(r"手动取消|用户取消|已暂停|task\s*cancelled|task\s*paused", all_text, re.I):
        return (
            "任务已被手动取消/暂停",
            "该任务是由用户手动停止或暂停的，并非网络故障或远程服务端异常。\n"
            "【解决建议】如需继续下载，可点击任务列表右侧的继续/重试按钮重新启动下载。"
        )

    # 0.1 临时目录占用异常检测
    if re.search(r"being\s*used\s*by\s*another\s*process|RemoveDirectoryInternal|SafeDeleteDir", all_text, re.I):
        return (
            "临时分片目录被系统占用",
            "分片下载已顺利完成，但在下载引擎尝试清理临时分片存储目录时，受到系统文件句柄锁定。\n"
            "【解决建议】视频分片已完整保存，系统会自动调用 FFmpeg 进行无损封装；请直接前往下载目录查看已生成的视频文件。"
        )

    url_str = str(url).strip()
    if url_str.startswith("blob:"):
        return (
            "无效地址 (blob: 临时内存流)",
            "blob: 是浏览器前端在内存中生成的临时流对象，并非实际网络资源地址。\n"
            "【解决建议】请在浏览器播放视频后，在星流嗅探扩展中查找实际的 .m3u8 清单或 .ts / .mp4 直链下载。"
        )

    # 过滤时间戳（如 23:21:56.504）与纯数字段，避免毫秒数或版本号误触发 HTTP 状态码正则
    text_clean = re.sub(r"\d{1,2}:\d{2}:\d{2}(?:\.\d+)?", " ", all_text)

    # 1. HTTP 403 Forbidden
    if re.search(r"(?:HTTP[/\s]*(?:status|code|response)?[:\s]*403\b|forbidden|status\s*code\s*[:=]?\s*403\b)", text_clean, re.I):
        return (
            "HTTP 403 权限被拒绝 (防盗链 / 链接鉴权过期)",
            "目标站点启用了防盗链安全机制，或者当前视频链接的访问 Token/时间戳鉴权已过期失效。\n"
            "【解决建议】请在浏览器中重新打开播放网页并刷新，待视频起播后，通过扩展插件嗅探并发送最新的有效地址；若该站有防盗链，请确认是否带上了 Referer 请求头。"
        )

    # 2. HTTP 401 Unauthorized
    if re.search(r"(?:HTTP[/\s]*(?:status|code|response)?[:\s]*401\b|unauthorized|status\s*code\s*[:=]?\s*401\b)", text_clean, re.I):
        return (
            "HTTP 401 访问未授权 (需登录或专用凭证)",
            "该视频流需要网站账号登录权限或特定 Cookie/Authorization 头鉴权。\n"
            "【解决建议】请确认在浏览器中已登录该视频网站账号，并使用嗅探扩展自动捕获的包含 Cookie/Header 的请求。"
        )

    # 3. HTTP 404 Not Found
    if re.search(r"(?:HTTP[/\s]*(?:status|code|response)?[:\s]*404\b|not\s*found|status\s*code\s*[:=]?\s*404\b)", text_clean, re.I):
        return (
            "HTTP 404 资源不存在",
            "目标视频 M3U8 清单或媒体分片在远程服务器上不存在或已被下架删除。\n"
            "【解决建议】请检查视频是否已失效或在网页端重新播放以获取最新地址。"
        )

    # 4. HTTP 429 Too Many Requests
    if re.search(r"(?:HTTP[/\s]*(?:status|code|response)?[:\s]*429\b|too\s*many\s*requests|status\s*code\s*[:=]?\s*429\b)", text_clean, re.I):
        return (
            "HTTP 429 请求过于频繁 (触发站点限流)",
            "向目标流媒体服务器发起的并发请求频率过高，触发了服务端的防爬/限流阈值。\n"
            "【解决建议】请在【设置】中将分片下载并发线程数调小（建议降为 4 ~ 8 线程），稍后重新开始任务。"
        )

    # 5. HTTP 5xx Server Error（严格匹配 HTTP 上下文，彻底防止毫秒 504 误判）
    if re.search(r"(?:HTTP[/\s]*(?:status|code|response)?[:\s]*(?:500|502|503|504)\b|bad\s*gateway|service\s*unavailable|gateway\s*time-?out|internal\s*server\s*error|status\s*code\s*[:=]?\s*(?:500|502|503|504)\b)", text_clean, re.I):
        return (
            "HTTP 5xx 远程服务器异常",
            "目标流媒体服务器内部发生故障、宕机或反向代理网关超时，非本地软件原因。\n"
            "【解决建议】请稍后再次重试，或在网页上确认视频是否能正常流畅播放。"
        )

    # 6. DNS 域名解析失败
    if re.search(r"不知道这样的主机|could\s*not\s*be\s*resolved|Name\s*or\s*service\s*not\s*known|nodename\s*nor\s*servname", all_text, re.I):
        return (
            "DNS 域名解析失败",
            "无法解析目标服务器的主机名。\n"
            "【解决建议】请检查网络连接是否通畅，若开启了本地代理，请检查代理客户端是否正常运行或关闭代理尝试直连。"
        )

    # 7. 代理连接被拒绝 / 端口未启动
    if re.search(r"积极拒绝|actively\s*refused|connection\s*refused|ProxyError|Proxy\s*connection\s*failed", all_text, re.I):
        return (
            "网络连接被拒绝 (代理端口未开启或失效)",
            "无法与目标服务器或指定的本地代理端口建立连接。\n"
            "【解决建议】如果您配置了本地代理（如 Clash 7890、v2rayN 10808），请确认代理客户端已在后台启动；若不需要代理，请在【设置】中将代理模式切换为“直连模式”。"
        )

    # 8. 网络超时
    if re.search(r"timed?\s*out|连接超时|操作已超时|The\s*operation\s*has\s*timed\s*out", all_text, re.I):
        return (
            "网络连接超时",
            "连接目标流媒体服务器时超时无响应，可能是网络波动严重、跨国节点延迟高或被防火墙拦截。\n"
            "【解决建议】请检查网络环境，或在【设置】中配置可用代理加速后重试。"
        )

    # 9. SSL / 证书握手失败
    if re.search(r"SSL|certificate|CERTIFICATE_VERIFY_FAILED|handshake", all_text, re.I):
        return (
            "SSL/TLS 加密证书验证失败",
            "与远程服务器建立安全 HTTPS 传输连接失败，可能是系统证书链不完整或受到网络中间人干扰。"
        )

    # 10. AES-128 / DRM 解密失败 (需匹配真实解密异常关键词，避免误报正常的 Vid*AES_128 清单规格)
    if re.search(r"Failed\s*to\s*decrypt|解密失败|解密密钥错误|无法获取.*?(?:密钥|key)|decrypt\s*error|DRM\s*protected|Widevine|PlayReady|FairPlay", all_text, re.I):
        return (
            "切片解密失败 (AES 密钥无法获取或受 DRM 版权保护)",
            "该视频流使用了加密保护，下载器未能从清单中声明的 Key 地址获取到解密密钥，或者该视频采用了商用不可逆 DRM 数字版权保护。\n"
            "【解决建议】此类型加密流无法直接离线下载，建议使用屏幕录制工具保存。"
        )

    # 11. 未能匹配有效流媒体
    if re.search(r"No\s*media\s*streams\s*found|未从\s*M3U8\s*中解析到任何分片|Invalid\s*playlist|无法识别的流", all_text, re.I):
        return (
            "未识别到可用的流媒体内容",
            "下载器未能从给定的 URL 中解析出有效的音视频切片列表。\n"
            "【解决建议】请确认嗅探到的链接是标准 M3U8 清单或实际流地址，而非网页 HTML 页面。"
        )

    # 12. FFmpeg 错误
    if re.search(r"ffmpeg|FFmpeg|Invalid\s*data\s*found\s*when\s*processing\s*input", all_text, re.I):
        return (
            "FFmpeg 音视频合并处理异常",
            "分片下载已完成，但在调用 FFmpeg 进行无损拼接封装或转码为 MP4 时发生错误。\n"
            "【解决建议】请进入软件上方【设置】检查 FFmpeg 校验状态，或取消勾选“自动转封装为标准 MP4”后重试。"
        )

    # 13. 磁盘空间不足
    if re.search(r"not\s*enough\s*space|空间不足|Disk\s*full|No\s*space\s*left", all_text, re.I):
        return (
            "磁盘存储空间不足",
            "目标下载目录所在的磁盘分区剩余空间不足，无法写入下载文件或合并后的完整视频。\n"
            "【解决建议】请清理目标磁盘分区空间，或在【设置】中更换保存目录至有充足空间的盘符。"
        )

    # 14. 权限受限
    if re.search(r"Permission\s*denied|拒绝访问|没有权限|Access\s*is\s*denied", all_text, re.I):
        return (
            "磁盘文件写入权限受限",
            "软件没有权限在目标保存目录创建或写入文件。\n"
            "【解决建议】请在【设置】中将保存目录更换至常用非系统盘目录（如 D:\\Downloads），或右键“以管理员身份运行”本软件。"
        )

    # 15. 默认兜底诊断
    clean_msg = error_msg.strip() if error_msg else "下载引擎进程异常终止"
    return (
        clean_msg,
        "下载引擎在执行过程中发生异常退出。请查阅下方完整的运行控制台日志，或查看 Logs/download_errors.log 获取详细执行栈。"
    )


def record_download_error(task_data, raw_error="", log_lines=None):
    """
    记录下载失败日志至 Logs/download_errors.log，并输出单任务日志 Logs/task_{id}.log
    返回: (diagnostic_title, diagnostic_hint, log_file_path)
    """
    ensure_logs_dir()
    task_id = task_data.get("id", "unknown")
    title = task_data.get("title") or "未命名任务"
    url = task_data.get("url") or ""
    media_type = task_data.get("media_type") or "未知"
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    diag_title, diag_hint = diagnose_error(log_lines, raw_error, url)

    # 1. 写入单任务独立日志 Logs/task_{task_id}.log
    task_log_file = os.path.join(LOGS_DIR, f"task_{task_id}.log")
    try:
        with open(task_log_file, "w", encoding="utf-8") as f:
            f.write(f"================================================================================\n")
            f.write(f"星流 (StarStream) 任务运行日志\n")
            f.write(f"记录时间: {now_str}\n")
            f.write(f"任务编号: {task_id}\n")
            f.write(f"媒体标题: {title}\n")
            f.write(f"媒体类型: {media_type}\n")
            f.write(f"资源地址: {url}\n")
            f.write(f"失败诊断: {diag_title}\n")
            f.write(f"解决建议: {diag_hint}\n")
            f.write(f"原始报错: {raw_error}\n")
            f.write(f"================================================================================\n\n")
            f.write(f"--- 运行控制台实时输出日志 ---\n")
            if log_lines:
                for line in log_lines:
                    f.write(f"{line}\n")
            else:
                f.write("(无控制台日志记录)\n")
    except Exception as e:
        print(f"[Logger] 写入单任务日志失败: {e}")

    # 2. 追加到全局错误汇总日志 Logs/download_errors.log
    try:
        with open(MASTER_ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n================================================================================\n")
            f.write(f"[{now_str}] 任务下载失败记录\n")
            f.write(f"--------------------------------------------------------------------------------\n")
            f.write(f"任务编号: {task_id}\n")
            f.write(f"媒体标题: {title}\n")
            f.write(f"媒体类型: {media_type}\n")
            f.write(f"资源地址: {url}\n")
            f.write(f"失败诊断: {diag_title}\n")
            f.write(f"解决建议:\n{diag_hint}\n")
            f.write(f"原始报错: {raw_error}\n")
            f.write(f"--------------------------------------------------------------------------------\n")
            f.write(f"[最后运行日志摘要]\n")
            if log_lines:
                # 记录最后 40 行日志
                recent = log_lines[-40:] if len(log_lines) > 40 else log_lines
                for line in recent:
                    f.write(f"{line}\n")
            else:
                f.write("(无控制台日志记录)\n")
            f.write(f"================================================================================\n")
    except Exception as e:
        print(f"[Logger] 追加全局错误日志失败: {e}")

    return diag_title, diag_hint, task_log_file
