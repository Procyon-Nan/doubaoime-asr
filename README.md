# doubaoime-asr

豆包输入法语音识别 Python 客户端。

## 免责声明

本项目通过对安卓豆包输入法客户端通信协议分析并参考客户端代码实现，**非官方提供的 API**。

- 本项目仅供学习和研究目的
- 不保证未来的可用性和稳定性
- 服务端协议可能随时变更导致功能失效

## 安装

```bash
# 从本地安装
git clone https://github.com/starccy/doubaoime-asr.git
cd doubaoime-asr
pip install -e .

# 或从 Git 仓库安装
pip install git+https://github.com/starccy/doubaoime-asr.git
```

### 系统依赖

本项目依赖 Opus 音频编解码库，需要先安装系统库：

```bash
# Debian/Ubuntu
sudo apt install libopus0

# Arch Linux
sudo pacman -S opus

# macOS
brew install opus
```

## 快速开始

### 基本用法

```python
import asyncio
from doubaoime_asr import transcribe, ASRConfig

async def main():
    # 配置（首次运行会自动注册设备，并将凭据保存到指定文件）
    config = ASRConfig(credential_path="./credentials.json")

    # 识别音频文件
    result = await transcribe("audio.wav", config=config)
    print(f"识别结果: {result}")

asyncio.run(main())
```

### 流式识别

如果需要获取中间结果或更详细的状态信息，可以使用 `transcribe_stream`：

```python
import asyncio
from doubaoime_asr import transcribe_stream, ASRConfig, ResponseType

async def main():
    config = ASRConfig(credential_path="./credentials.json")

    async for response in transcribe_stream("audio.wav", config=config):
        match response.type:
            case ResponseType.INTERIM_RESULT:
                print(f"[中间结果] {response.text}")
            case ResponseType.FINAL_RESULT:
                print(f"[最终结果] {response.text}")
            case ResponseType.ERROR:
                print(f"[错误] {response.error_msg}")

asyncio.run(main())
```

### 实时麦克风识别

实时语音识别需要配合音频采集库使用，请参考 [examples/mic_realtime.py](examples/mic_realtime.py)。

运行示例需要安装额外依赖：

```bash
pip install sounddevice numpy
# 或
pip install doubaoime-asr[examples]
```

## API 参考

### transcribe

非流式语音识别，直接返回最终结果。

```python
async def transcribe(
    audio: str | Path | bytes,
    *,
    config: ASRConfig | None = None,
    on_interim: Callable[[str], None] | None = None,
    realtime: bool = False,
) -> str
```

参数：
- `audio`: 音频文件路径或 PCM 字节数据
- `config`: ASR 配置
- `on_interim`: 中间结果回调
- `realtime`: 是否模拟实时发送（每个音频数据帧之间加入固定的发送延迟）
    - `True`: 模拟实时发送，加入固定的延迟，表现得更像正常的客户端，但会增加整体识别时间
    - `False`: 尽可能快地发送所有数据帧，整体识别时间更短（貌似也不会被风控）

### transcribe_stream

流式语音识别，返回 `ASRResponse` 异步迭代器。

```python
async def transcribe_stream(
    audio: str | Path | bytes,
    *,
    config: ASRConfig | None = None,
    realtime: bool = False,
) -> AsyncIterator[ASRResponse]
```

### transcribe_realtime

实时流式语音识别，接收 PCM 音频数据的异步迭代器。

```python
async def transcribe_realtime(
    audio_source: AsyncIterator[bytes],
    *,
    config: ASRConfig | None = None,
) -> AsyncIterator[ASRResponse]
```

### ASRConfig

配置类，支持以下主要参数：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `credential_path` | str | None | 凭据缓存文件路径 |
| `device_id` | str | None | 设备 ID（空则自动注册） |
| `token` | str | None | 认证 Token（空则自动获取） |
| `sample_rate` | int | 16000 | 采样率 |
| `channels` | int | 1 | 声道数 |
| `enable_punctuation` | bool | True | 是否启用标点 |

### ResponseType

响应类型枚举：

| 类型 | 说明 |
|------|------|
| `TASK_STARTED` | 任务已启动 |
| `SESSION_STARTED` | 会话已启动 |
| `VAD_START` | 检测到语音开始 |
| `INTERIM_RESULT` | 中间识别结果 |
| `FINAL_RESULT` | 最终识别结果 |
| `SESSION_FINISHED` | 会话结束 |
| `ERROR` | 错误 |

## 凭据管理

首次使用时会自动向服务器注册虚拟设备（设备参数定义在 `constants.py` 的 `DEFAULT_DEVICE_CONFIG` 中）并获取认证 Token。

推荐指定 `credential_path` 参数，凭据会自动缓存到文件，避免重复注册：

```python
config = ASRConfig(credential_path="~/.config/doubaoime-asr/credentials.json")
```

## API 服务

项目根目录新增了 `api/` 目录，用于把现有能力封装成一个轻量 HTTP API 服务，同时保留原有 ESP32 桥接接收方式。

### 启动方式

可以直接运行新的 API 入口：

```bash
python3 -m api.cli
```

在 Linux 环境下，也可以直接使用根目录的启动脚本：

```bash
chmod +x ./start.sh
./start.sh
```

也可以继续沿用原有脚本启动方式：

```bash
python3 examples/esp32_asr_bridge.py
```

默认启动后会提供以下接口：

- 旧兼容接口：`POST /asr/transcribe`
- 新标准接口：`POST /v1/stt/transcriptions`
- Aliyun 兼容接口：`POST /stream/v1/asr`
- 健康检查：`GET /healthz`

默认参数：

- `--host 0.0.0.0`
- `--port 9000`
- `--path /asr/transcribe`
- `--standard-path /v1/stt/transcriptions`
- `--aliyun-path /stream/v1/asr`
- `--health-path /healthz`
- `--credential-path ./credentials.json`
- `--max-body-bytes 320000`

示例：

```bash
python3 -m api.cli --host 0.0.0.0 --port 9000 --credential-path ./credentials.json
```

### 旧 ESP32 兼容接口

保持原有请求方式不变：

```http
POST /asr/transcribe
Content-Type: application/octet-stream
X-Sample-Rate: 16000
X-Channels: 1
X-Audio-Format: pcm_s16le
X-Device-Id: esp32-001

<raw pcm bytes>
```

请求要求：

- body 为原始 PCM 字节流
- 默认音频格式为 `16kHz / mono / pcm_s16le`
- `X-Audio-Format` 当前仅支持 `pcm_s16le`

成功响应：

```json
{
  "ok": true,
  "text": "识别结果"
}
```

失败响应示例：

```json
{
  "ok": false,
  "error": "unsupported audio format"
}
```

### 标准 STT 接口

新增通用转写接口：

```http
POST /v1/stt/transcriptions
```

目前支持两种请求格式。

#### 1. application/json + base64 音频

请求示例：

```json
{
  "audio": {
    "content_base64": "<base64 audio>",
    "format": "pcm_s16le",
    "sample_rate": 16000,
    "channels": 1
  },
  "options": {
    "enable_punctuation": true,
    "realtime": true
  },
  "device_id": "client-1"
}
```

#### 2. multipart/form-data

表单字段：

- `file`: 音频文件或音频字节
- `format`: 音频格式，当前仅支持 `pcm_s16le`
- `sample_rate`: 采样率
- `channels`: 声道数
- `device_id`: 设备标识（可选）
- `enable_punctuation`: 是否启用标点（可选）
- `realtime`: 是否按实时节奏发送（可选）

成功响应：

```json
{
  "ok": true,
  "text": "识别结果",
  "segments": ["第一段", "第二段"],
  "meta": {
    "audio_format": "pcm_s16le",
    "sample_rate": 16000,
    "channels": 1,
    "device_id": "client-1"
  }
}
```

失败响应示例：

```json
{
  "ok": false,
  "error": "invalid json body"
}
```

### Aliyun 兼容接口

为了兼容 `TouhouLittleMaid` 现有的 `aliyun` STT 请求方式，API 服务额外提供：

```http
POST /stream/v1/asr
```

这个接口不是直连阿里云，而是返回 **Aliyun 风格响应**，内部仍然使用当前项目已有的豆包识别能力。

#### 请求格式

请求头：

- `Content-Type: application/octet-stream`
- `X-NLS-Token: <token>`（当前仅作兼容读取，可为空）

Query 参数中至少需要：

- `appkey=<any-value>`
- `format=wav`
- `sample_rate=16000`
- `enable_punctuation_prediction=true|false`

其余像 `enable_inverse_text_normalization`、`enable_voice_detection`、`disfluency`、`vocabulary_id`、`customization_id` 等参数可以继续传入，服务会兼容接收，但当前不会参与内部识别逻辑。

请求体要求：

- body 必须是完整 **WAV** 音频字节
- WAV 采样宽度当前仅支持 `16-bit`
- 服务会在接口层先解包 WAV，再把 PCM 数据送入内部识别流程

请求示例：

```bash
curl -X POST \
  "http://127.0.0.1:9000/stream/v1/asr?appkey=test&format=wav&sample_rate=16000&enable_punctuation_prediction=true" \
  -H "Content-Type: application/octet-stream" \
  -H "X-NLS-Token: test-token" \
  --data-binary @test/test_audio.wav
```

成功响应示例：

```json
{
  "task_id": "",
  "result": "识别结果",
  "status": 20000000,
  "message": "SUCCESS"
}
```

失败响应示例：

```json
{
  "task_id": "",
  "result": "",
  "status": 40000006,
  "message": "invalid wav body"
}
```

#### TouhouLittleMaid 对接

如果你使用的是 `TouhouLittleMaid` 中的 `aliyun` STT 实现，可以把它的站点地址改成你的服务地址，例如：

```text
http://<server>:9000/stream/v1/asr
```

然后继续按它原本的方式发送：

- `application/octet-stream`
- WAV 音频 body
- `X-NLS-Token`
- URL query 参数

客户端只要收到 HTTP 2xx 且响应 JSON 中 `status == 20000000`，就会把 `result` 当作最终识别文本。

### 测试脚本

项目根目录新增了 `test/` 目录，提供了简单测试脚本：

- `test/test_health.py`：测试 `/healthz`
- `test/test_api.py`：同时测试旧兼容接口和新标准接口
- `test/generate_test_pcm.py`：生成 `pcm_s16le` 测试音频

示例：

```bash
python3 test/test_health.py --host 127.0.0.1 --port 9000
python3 test/test_api.py ./audio.pcm --host 127.0.0.1 --port 9000
python3 test/test_api.py ./audio.pcm --host 127.0.0.1 --port 9000 --multipart
python3 test/generate_test_pcm.py
python3 test/generate_test_pcm.py ./test/test_audio.pcm --duration 3 --frequency 523.25 --wav
```

