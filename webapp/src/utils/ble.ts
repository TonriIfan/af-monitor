/**
 * 浏览器侧智能戒指 BLE 连接封装。
 *
 * 对齐 study/ble/utils/btls/ 中小程序的 service / characteristic UUID 设计，
 * 只暴露最小的 API 供上层调用：connect / disconnect / write / onFrame。
 *
 * 注意：Web Bluetooth API 只在 Chrome / Edge / Opera 等 Blink 浏览器中可用，
 * 且必须在 HTTPS 或 localhost 下运行，首次 requestDevice 必须由用户手势触发。
 */

export const RING_SERVICE_UUID = 'bae80001-4f05-4503-8e65-3af1f7329d1f'
export const RING_WRITE_UUID = 'bae80010-4f05-4503-8e65-3af1f7329d1f'
export const RING_NOTIFY_UUID = 'bae80011-4f05-4503-8e65-3af1f7329d1f'

export type BleState = 'idle' | 'connecting' | 'connected' | 'disconnected' | 'error'

export type FrameListener = (frame: Uint8Array) => void
export type StateListener = (state: BleState, detail?: string) => void

export interface RingDeviceInfo {
  id: string
  name: string
}

export function isWebBluetoothSupported(): boolean {
  return typeof navigator !== 'undefined' && typeof navigator.bluetooth !== 'undefined'
}

export async function isBluetoothAvailable(): Promise<boolean> {
  if (!isWebBluetoothSupported()) return false
  try {
    return await navigator.bluetooth.getAvailability()
  } catch {
    return true
  }
}

class RingBleClient {
  private device: BluetoothDevice | null = null
  private writeChar: BluetoothRemoteGATTCharacteristic | null = null
  private notifyChar: BluetoothRemoteGATTCharacteristic | null = null
  private frameListeners = new Set<FrameListener>()
  private stateListeners = new Set<StateListener>()
  private state: BleState = 'idle'

  getState(): BleState {
    return this.state
  }

  getDevice(): RingDeviceInfo | null {
    if (!this.device) return null
    return { id: this.device.id, name: this.device.name || '(未命名)' }
  }

  onFrame(listener: FrameListener): () => void {
    this.frameListeners.add(listener)
    return () => this.frameListeners.delete(listener)
  }

  onStateChange(listener: StateListener): () => void {
    this.stateListeners.add(listener)
    // 立即推送当前状态
    listener(this.state)
    return () => this.stateListeners.delete(listener)
  }

  private setState(next: BleState, detail?: string) {
    this.state = next
    this.stateListeners.forEach((fn) => {
      try {
        fn(next, detail)
      } catch {
        /* ignore */
      }
    })
  }

  async connect(): Promise<RingDeviceInfo> {
    if (!isWebBluetoothSupported()) {
      throw new Error('当前浏览器不支持 Web Bluetooth，请使用 Chrome / Edge。')
    }
    if (this.state === 'connecting' || this.state === 'connected') {
      throw new Error('已在连接中或已连接，无需重复连接。')
    }
    this.setState('connecting')
    try {
      const device = await navigator.bluetooth.requestDevice({
        acceptAllDevices: true,
        optionalServices: [RING_SERVICE_UUID],
      })
      this.device = device
      device.addEventListener('gattserverdisconnected', this.handleDisconnected)

      if (!device.gatt) {
        throw new Error('设备不支持 GATT。')
      }
      const server = await device.gatt.connect()
      const service = await server.getPrimaryService(RING_SERVICE_UUID)
      this.writeChar = await service.getCharacteristic(RING_WRITE_UUID)
      this.notifyChar = await service.getCharacteristic(RING_NOTIFY_UUID)

      this.notifyChar.addEventListener('characteristicvaluechanged', this.handleFrame)
      await this.notifyChar.startNotifications()

      this.setState('connected')
      return { id: device.id, name: device.name || '(未命名)' }
    } catch (err) {
      this.setState('error', err instanceof Error ? err.message : String(err))
      await this.safeCleanup()
      throw err
    }
  }

  async disconnect(): Promise<void> {
    await this.safeCleanup()
    this.setState('disconnected')
  }

  async write(data: Uint8Array): Promise<void> {
    if (!this.writeChar) {
      throw new Error('设备尚未连接。')
    }
    // Web Bluetooth 期望一个 ArrayBuffer 视图；把输入复制进一块新的 ArrayBuffer，
    // 避免 Uint8Array<ArrayBufferLike> 与 BufferSource 的类型窄化冲突。
    const buffer = new ArrayBuffer(data.byteLength)
    new Uint8Array(buffer).set(data)
    if (this.writeChar.writeValueWithoutResponse) {
      await this.writeChar.writeValueWithoutResponse(buffer)
    } else {
      await this.writeChar.writeValue(buffer)
    }
  }

  private handleFrame = (evt: Event) => {
    const char = evt.target as BluetoothRemoteGATTCharacteristic
    const value = char.value
    if (!value) return
    const bytes = new Uint8Array(value.buffer.slice(value.byteOffset, value.byteOffset + value.byteLength))
    this.frameListeners.forEach((fn) => {
      try {
        fn(bytes)
      } catch {
        /* ignore */
      }
    })
  }

  private handleDisconnected = () => {
    this.writeChar = null
    this.notifyChar = null
    this.setState('disconnected', '设备连接已断开')
  }

  private async safeCleanup(): Promise<void> {
    try {
      if (this.notifyChar) {
        try {
          await this.notifyChar.stopNotifications()
        } catch {
          /* ignore */
        }
        this.notifyChar.removeEventListener('characteristicvaluechanged', this.handleFrame)
      }
    } catch {
      /* ignore */
    }
    try {
      if (this.device?.gatt?.connected) {
        this.device.gatt.disconnect()
      }
    } catch {
      /* ignore */
    }
    this.writeChar = null
    this.notifyChar = null
  }
}

/**
 * 全局单例。浏览器标签页内只维持一个 BLE 客户端。
 */
export const ringBle = new RingBleClient()
