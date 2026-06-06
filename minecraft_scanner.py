"""
Minecraft Server Scanner - асинхронный сканер локальных серверов Minecraft
"""
import asyncio
import socket
import struct
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class MinecraftVersion(Enum):
    """Версии Minecraft Java Edition"""
    V1_20 = 760  # Minecraft 1.20.x
    V1_19 = 759  # Minecraft 1.19.x
    V1_18 = 758  # Minecraft 1.18.x
    V1_17 = 757  # Minecraft 1.17.x
    V1_16 = 754  # Minecraft 1.16.x
    LATEST = 760  # Последняя версия


@dataclass
class ServerInfo:
    """Информация о найденном сервере"""
    host: str
    port: int
    motd: str
    version: str
    protocol_version: int
    players_online: int
    players_max: int
    latency: float
    online: bool = True

    def __repr__(self):
        return (f"Server({self.host}:{self.port}, "
                f"Players: {self.players_online}/{self.players_max}, "
                f"Latency: {self.latency:.0f}ms)")


class MinecraftServerScanner:
    """Сканер серверов Minecraft используя Server List Ping протокол"""

    MINECRAFT_PORT = 25565
    TIMEOUT = 3  # секунды
    PROTOCOL_VERSION = MinecraftVersion.V1_20.value

    def __init__(self, target_versions: Optional[List[int]] = None):
        """
        Инициализация сканера

        Args:
            target_versions: Список допустимых версий протокола (protocol version)
        """
        self.target_versions = target_versions or [
            MinecraftVersion.V1_20.value,
            MinecraftVersion.V1_19.value,
            MinecraftVersion.V1_18.value,
        ]
        self.servers: List[ServerInfo] = []

    async def ping_server(self, host: str, port: int = MINECRAFT_PORT) -> Optional[ServerInfo]:
        """
        Проверка сервера по протоколу Server List Ping (1.7+)

        Args:
            host: IP адрес сервера
            port: Порт сервера (по умолчанию 25565)

        Returns:
            ServerInfo если сервер отвечает, иначе None
        """
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=self.TIMEOUT
            )

            # Создаем Handshake пакет
            handshake = self._create_handshake_packet(host, port)
            writer.write(handshake)
            await writer.drain()

            # Отправляем Status Request
            status_request = bytes([0x00])  # Пакет длины 1 с типом 0x00
            writer.write(self._wrap_packet(status_request))
            await writer.drain()

            # Читаем ответ Status Response
            response = await asyncio.wait_for(
                reader.read(1024),
                timeout=self.TIMEOUT
            )

            writer.close()
            await writer.wait_closed()

            if not response:
                return None

            # Парсим ответ
            server_info = self._parse_status_response(response, host, port)
            return server_info

        except (asyncio.TimeoutError, ConnectionRefusedError, OSError):
            return None
        except Exception as e:
            print(f"Ошибка при проверке {host}:{port} - {e}")
            return None

    def _create_handshake_packet(self, host: str, port: int) -> bytes:
        """Создает Handshake пакет для Server List Ping"""
        packet = bytearray()

        # Packet ID: 0x00 для Handshake
        packet.append(0x00)

        # Protocol Version (VarInt)
        packet.extend(self._encode_varint(self.PROTOCOL_VERSION))

        # Server Address (String)
        host_bytes = host.encode('utf-8')
        packet.extend(self._encode_varint(len(host_bytes)))
        packet.extend(host_bytes)

        # Server Port (Short)
        packet.extend(struct.pack('>H', port))

        # Next State (VarInt) - 1 для Status
        packet.append(0x01)

        return self._wrap_packet(bytes(packet))

    def _wrap_packet(self, packet: bytes) -> bytes:
        """Оборачивает пакет с его размером (VarInt)"""
        length = len(packet)
        return self._encode_varint(length) + packet

    @staticmethod
    def _encode_varint(value: int) -> bytes:
        """Кодирует число в VarInt (Minecraft протокол)"""
        result = bytearray()
        while True:
            byte = value & 0x7F
            value >>= 7
            if value != 0:
                byte |= 0x80
            result.append(byte)
            if value == 0:
                break
        return bytes(result)

    @staticmethod
    def _decode_varint(data: bytes, offset: int = 0) -> Tuple[int, int]:
        """
        Декодирует VarInt из данных

        Returns:
            Кортеж (значение, количество прочитанных байт)
        """
        result = 0
        shift = 0
        i = 0
        while True:
            byte = data[offset + i]
            i += 1
            result |= (byte & 0x7F) << shift
            if (byte & 0x80) == 0:
                break
            shift += 7
        return result, i

    def _parse_status_response(self, data: bytes, host: str, port: int) -> Optional[ServerInfo]:
        """
        Парсит ответ Status Response от сервера

        Формат:
        - Packet Length (VarInt)
        - Packet ID (VarInt) - 0x00 для Status Response
        - JSON Response (String)
        """
        try:
            offset = 0

            # Пропускаем длину пакета
            _, bytes_read = self._decode_varint(data, offset)
            offset += bytes_read

            # Читаем Packet ID
            packet_id, bytes_read = self._decode_varint(data, offset)
            offset += bytes_read

            if packet_id != 0x00:
                return None

            # Читаем JSON строку (String = VarInt длина + данные)
            json_length, bytes_read = self._decode_varint(data, offset)
            offset += bytes_read

            json_bytes = data[offset:offset + json_length]
            json_str = json_bytes.decode('utf-8')

            # Простой парсинг JSON без библиотек
            import json
            json_data = json.loads(json_str)

            # Извлекаем информацию
            version_info = json_data.get('version', {})
            players_info = json_data.get('players', {})
            description = json_data.get('description', {})

            protocol_version = version_info.get('protocol', 0)

            # Проверяем версию
            if protocol_version not in self.target_versions:
                return None

            # Форматируем MOTD (может быть строка или объект)
            if isinstance(description, dict):
                motd = description.get('text', 'Unknown')
            else:
                motd = str(description)

            version_name = version_info.get('name', 'Unknown')
            players_online = players_info.get('online', 0)
            players_max = players_info.get('max', 0)

            return ServerInfo(
                host=host,
                port=port,
                motd=motd,
                version=version_name,
                protocol_version=protocol_version,
                players_online=players_online,
                players_max=players_max,
                latency=self.TIMEOUT * 1000,  # Примерная задержка
            )

        except Exception as e:
            print(f"Ошибка парсинга ответа от {host}:{port} - {e}")
            return None

    async def scan_range(self, base_ip: str, start: int = 1, end: int = 100,
                        port: int = MINECRAFT_PORT,
                        callback=None) -> List[ServerInfo]:
        """
        Сканирует диапазон IP адресов

        Args:
            base_ip: Базовый IP (например: "192.168.1")
            start: Начальный октет
            end: Конечный октет
            port: Порт для сканирования
            callback: Функция обратного вызова для каждой проверки

        Returns:
            Список найденных серверов
        """
        tasks = []
        for i in range(start, end + 1):
            host = f"{base_ip}.{i}"
            task = self.ping_server(host, port)
            tasks.append((host, task))

            if len(tasks) >= 100:  # Ограничиваем одновременные соединения
                results = await asyncio.gather(*[t[1] for t in tasks])
                for (host, _), server_info in zip(tasks, results):
                    if server_info:
                        self.servers.append(server_info)
                    if callback:
                        callback(host, server_info is not None)
                tasks = []

        # Обработаем оставшиеся задачи
        if tasks:
            results = await asyncio.gather(*[t[1] for t in tasks])
            for (host, _), server_info in zip(tasks, results):
                if server_info:
                    self.servers.append(server_info)
                if callback:
                    callback(host, server_info is not None)

        return self.servers

    async def scan_ips_concurrent(self, ip_list: List[str], port: int = MINECRAFT_PORT,
                                  max_concurrent: int = 50,
                                  callback=None) -> List[ServerInfo]:
        """
        Сканирует список IP адресов с ограничением одновременных соединений

        Args:
            ip_list: Список IP адресов
            port: Порт для сканирования
            max_concurrent: Максимальное количество одновременных соединений
            callback: Функция обратного вызова для каждой проверки

        Returns:
            Список найденных серверов
        """
        self.servers = []
        semaphore = asyncio.Semaphore(max_concurrent)

        async def scan_with_semaphore(host):
            async with semaphore:
                result = await self.ping_server(host, port)
                if result:
                    self.servers.append(result)
                if callback:
                    callback(host, result is not None)
                return result

        tasks = [scan_with_semaphore(host) for host in ip_list]
        await asyncio.gather(*tasks)

        return self.servers


def get_local_network_ip() -> str:
    """Определяет локальный IP адрес компьютера"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "192.168.1"


def generate_ip_range(base_ip: str, start: int = 1, end: int = 254) -> List[str]:
    """Генерирует список IP адресов в диапазоне"""
    return [f"{base_ip}.{i}" for i in range(start, end + 1)]


# Пример использования
if __name__ == "__main__":
    import sys

    async def main():
        print("🔍 Minecraft Server Scanner\n")

        # Получаем локальный IP
        local_ip = get_local_network_ip()
        base_ip = ".".join(local_ip.split(".")[:3])
        print(f"📍 Локальная сеть: {base_ip}.0/24\n")

        # Создаем сканер
        scanner = MinecraftServerScanner()

        # Генерируем список IP
        ip_list = generate_ip_range(base_ip, 1, 100)
        print(f"🔎 Сканирование {len(ip_list)} адресов...\n")

        def progress_callback(ip, found):
            status = "✅ НАЙДЕН!" if found else "❌"
            print(f"{status} {ip}")

        # Сканируем
        servers = await scanner.scan_ips_concurrent(ip_list, callback=progress_callback)

        # Выводим результаты
        print(f"\n{'='*60}")
        print(f"📊 Найдено серверов: {len(servers)}")
        print(f"{'='*60}\n")

        for server in servers:
            print(f"🎮 {server.host}:{server.port}")
            print(f"   Версия: {server.version}")
            print(f"   MOTD: {server.motd}")
            print(f"   Игроков онлайн: {server.players_online}/{server.players_max}")
            print(f"   Протокол: {server.protocol_version}")
            print()

    asyncio.run(main())
