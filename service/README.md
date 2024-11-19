# Services

## Installation

```sh
SERVICE_NAME=<service-name>
sudo cp -f "$SERVICE_NAME.service" "/etc/systemd/system/$SERVICE_NAME.service"
systemctl daemon-reload
service "$SERVICE_NAME" restart
systemctl enable "$SERVICE_NAME"
service "$SERVICE_NAME" status
```

## Monitoring

```sh
SERVICE_NAME=<service-name>
journalctl -f -n 50 -u $SERVICE_NAME
```

```sh
SERVICE_NAME=<service-name>
sudo tail -f /var/log/syslog | grep
```

## Removing services

```sh
SERVICE_NAME=<service-name>
systemctl stop $SERVICE_NAME
systemctl disable $SERVICE_NAME
rm -f "/etc/systemd/system/$SERVICE_NAME.service"
systemctl daemon-reload
systemctl reset-failed
```
