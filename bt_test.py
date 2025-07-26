from typing import NamedTuple

from PyQt6 import QtBluetooth
from PyQt6.QtWidgets import (QApplication, QComboBox, QMainWindow, QPushButton,
                             QVBoxLayout, QWidget)
from PyQt6.QtCore import QTimer


class BluetoothDeviceInfo(NamedTuple):
    name: str
    address: str
    uuid: QtBluetooth.QBluetoothUuid.ServiceClassUuid


class Window(QMainWindow):
    def __init__(
        self,
    ) -> None:
        super().__init__(None)
        self.bluetooth_discovery_agent: (
            QtBluetooth.QBluetoothDeviceDiscoveryAgent | None
        ) = None
        self.bluetooth_devices_found: list[
            BluetoothDeviceInfo
        ] = []
        self.bt_devices_found_previous: list[
            BluetoothDeviceInfo
        ] = []
        self.connected = False
        self.setup_ui()
        self.bluetooth_activate()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.read_bt)
        self.timer.start(100)

    def read_bt(self) -> None:
        if self.connected:
            print(self.sock.readLine())

    def setup_ui(self) -> None:
        widget = QWidget()
        self.setCentralWidget(widget)
        self.vbox_layout = QVBoxLayout()
        widget.setLayout(self.vbox_layout)
        self.scan_button = QPushButton("Scan")
        self.vbox_layout.addWidget(self.scan_button)
        self.devices_combo = QComboBox()
        self.vbox_layout.addWidget(self.devices_combo)
        self.connect_button = QPushButton("Connect")
        self.vbox_layout.addWidget(self.connect_button)

        self.scan_button.clicked.connect(self.bluetooth_activate)
        self.connect_button.clicked.connect(self.connect)

    def connect(self) -> None:
        device_name = self.devices_combo.currentText()
        for device in self.bluetooth_devices_found:
            if device.name == device_name:
                self.sock = QtBluetooth.QBluetoothSocket(
                    QtBluetooth.QBluetoothServiceInfo.Protocol.RfcommProtocol
                )
                self.sock.connected.connect(self.connected_to_bluetooth)
                self.sock.disconnected.connect(lambda: print("Disconnected"))
                self.sock.errorOccurred.connect(
                    lambda e: print("Error", e)
                )
                self.sock.connectToService(
                    QtBluetooth.QBluetoothAddress(device.address), device.uuid
                )
                return

    def connected_to_bluetooth(self) -> None:
        print("Connected")
        self.connected = True

    def bluetooth_device_discovered(
        self, info: QtBluetooth.QBluetoothDeviceInfo,
    ) -> None:
        print(
            f"Found Bluetooth Device {info.name()} at "
            f"{info.address().toString()}", "DEBUG",
        )
        if not info.serviceUuids():
            return
        device_info = BluetoothDeviceInfo(
            info.name(), info.address(), info.serviceUuids()[0])
        self.bluetooth_devices_found.append(device_info)

    def bluetooth_activate(self) -> None:
        self.bluetooth_devices_found.clear()
        if self.bluetooth_discovery_agent:
            self.bluetooth_discovery_agent.stop()
        del self.bluetooth_discovery_agent
        self.bluetooth_discovery_agent = (
            QtBluetooth.QBluetoothDeviceDiscoveryAgent()
        )
        self.bluetooth_discovery_agent.deviceDiscovered.connect(
            self.bluetooth_device_discovered
        )

        self.bluetooth_discovery_agent.finished.connect(self.update_devices)
        self.bluetooth_discovery_agent.errorOccurred.connect(
            lambda e: print("Error", e)
        )
        self.bluetooth_discovery_agent.start()

    def update_devices(self) -> None:
        self.devices_combo.clear()
        for device in self.bluetooth_devices_found:
            self.devices_combo.addItem(device.name)


app = QApplication([])
win = Window()
win.show()
app.exec()
