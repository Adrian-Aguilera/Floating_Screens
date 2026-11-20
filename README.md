# Floating Screens

Primera fase de una aplicación para compartir control entre PCs con Windows en una red local.

## Ejecutar

En ambas PCs, abre el proyecto y ejecuta `uv run floating-screens`. Se requiere Python 3.13 o posterior con Tk y OpenSSL con soporte TLS-PSK.

1. En la PC de destino, deja **Origen PC** desmarcado, pulsa **Activar recepción** y copia la **Security Key**. Si Windows solicita permiso de red, habilítalo para la red privada.
2. En la PC de origen, marca **Origen PC**, pulsa **+** y escribe el nombre de red del destino o su IPv4, seguido de la clave. Cada activación de la recepción genera una clave nueva.
3. Haz clic en el panel del origen para empezar a controlar. El panel representa la pantalla principal del destino. Puedes mover el cursor, hacer clic, usar la rueda y escribir en la aplicación activa del destino. Presiona **Esc** para soltar el control.
4. Para cambiar de equipo, desconecta la sesión y elige otro destino de la lista. Los destinos se conservan mientras la app esté abierta. En el destino, **Desactivar recepción** revoca la clave y cierra la sesión.

La conexión usa TCP 49731 con TLS 1.3 y autenticación mediante la clave compartida. La captura de ventanas, el video, el portapapeles y el descubrimiento automático quedan para fases posteriores.

## Código

- `ui/` contiene la selección de rol y el panel de control.
- `pairing/` genera las claves y configura TLS.
- `network/` gestiona las sesiones y el protocolo de mensajes.
- `input/` valida los eventos e interactúa con Windows.
