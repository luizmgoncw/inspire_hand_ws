# Configuracao de IP Forwarding para Maos Roboticas

Este documento descreve como configurar o PC2 (Jetson do robo H1) como gateway para permitir que o Server PC acesse as maos roboticas atraves da rede WiFi.

## Topologia de Rede

```
Server PC (192.168.31.x)
        |
        | WiFi (192.168.31.0/27)
        |
        v
PC2 - Jetson (192.168.31.15 + 192.168.123.164)
        |
        | Ethernet eth0 (192.168.123.0/24)
        |
        v
+-------+-------+
|               |
Mao Esquerda    Mao Direita
192.168.123.210 192.168.123.211
```

## Interfaces do PC2 (Jetson)

| Interface | IP | Rede | Descricao |
|-----------|-----|------|-----------|
| wlan0 | 192.168.31.15 | 192.168.31.0/27 | WiFi - conecta ao Server PC |
| eth0 | 192.168.123.164 | 192.168.123.0/24 | Ethernet - conecta as maos |

## Configuracao do PC2 (Jetson)

### 1. Habilitar IP Forwarding (temporario)

```bash
sudo sysctl -w net.ipv4.ip_forward=1
```

### 2. Configurar regras de NAT/Forwarding

```bash
# NAT para pacotes vindos da rede WiFi indo para a rede das maos
sudo iptables -t nat -A POSTROUTING -o eth0 -s 192.168.31.0/27 -j MASQUERADE

# Permitir forwarding de wlan0 para eth0
sudo iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT

# Permitir retorno de pacotes estabelecidos
sudo iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
```

### 3. Tornar configuracao permanente

```bash
# IP forwarding permanente
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf

# Instalar iptables-persistent
sudo apt install iptables-persistent -y

# Salvar regras do iptables
sudo netfilter-persistent save
```

## Configuracao do Server PC

### 1. Adicionar rota (temporario)

```bash
sudo ip route add 192.168.123.0/24 via 192.168.31.15
```

### 2. Tornar rota permanente

```bash
# Criar script de inicializacao
echo '#!/bin/bash
ip route add 192.168.123.0/24 via 192.168.31.15 2>/dev/null || true' | sudo tee /etc/networkd-dispatcher/routable.d/50-hand-route

sudo chmod +x /etc/networkd-dispatcher/routable.d/50-hand-route
```

## Verificacao

### No Server PC

```bash
# Verificar se a rota existe
ip route | grep 192.168.123

# Testar conectividade com as maos
ping 192.168.123.210
ping 192.168.123.211
```

### No PC2 (Jetson)

```bash
# Verificar IP forwarding
cat /proc/sys/net/ipv4/ip_forward
# Deve retornar: 1

# Verificar regras do iptables
sudo iptables -L -v
sudo iptables -t nat -L -v
```

## Troubleshooting

### Rota nao funciona apos reboot do Server PC

```bash
# Verificar se o script existe
ls -la /etc/networkd-dispatcher/routable.d/50-hand-route

# Adicionar rota manualmente
sudo ip route add 192.168.123.0/24 via 192.168.31.15
```

### IP forwarding desabilitado no PC2

```bash
# Verificar
cat /proc/sys/net/ipv4/ip_forward

# Habilitar
sudo sysctl -w net.ipv4.ip_forward=1
```

### Regras do iptables perdidas no PC2

```bash
# Recarregar regras salvas
sudo netfilter-persistent reload

# Ou recriar manualmente
sudo iptables -t nat -A POSTROUTING -o eth0 -s 192.168.31.0/27 -j MASQUERADE
sudo iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT
sudo iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
```

## Remover Configuracao

### No PC2 (Jetson)

```bash
# Remover regras do iptables
sudo iptables -t nat -D POSTROUTING -o eth0 -s 192.168.31.0/27 -j MASQUERADE
sudo iptables -D FORWARD -i wlan0 -o eth0 -j ACCEPT
sudo iptables -D FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT

# Salvar (limpar regras salvas)
sudo netfilter-persistent save

# Remover linha do sysctl.conf
sudo sed -i '/net.ipv4.ip_forward=1/d' /etc/sysctl.conf
```

### No Server PC

```bash
# Remover rota
sudo ip route del 192.168.123.0/24 via 192.168.31.15

# Remover script
sudo rm /etc/networkd-dispatcher/routable.d/50-hand-route
```
