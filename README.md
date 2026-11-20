# Floating Screens

Comparte una ventana de Windows con otra PC en la red local. La aplicación sigue ejecutándose en el origen. En el destino, puedes mover y redimensionar el espejo como cualquier otra ventana.

## Compartir una ventana

1. Ejecuta `uv run floating-screens` en ambas PCs. Usa la misma versión en los dos equipos. Se requiere Windows 10 versión 1903 o posterior, Windows x64 y Python 3.13 con Tk y TLS-PSK.
2. En el destino, deja **Origen PC** desmarcado, pulsa **Activar recepción** y copia la **Security Key**. Cada activación genera una clave nueva. Autoriza el acceso en la red privada si Windows solicita permiso.
3. En el origen, marca **Origen PC** y pulsa **+ Añadir pantalla**. Introduce el nombre de red o IPv4 del destino y su clave. Elige el monitor remoto, el monitor local y un borde que esté libre. Puedes pulsar la tarjeta del destino para cambiar la asignación.
4. Arrastra la ventana activa desde su barra de título y suéltala en el borde asignado. El espejo se abre junto al borde correspondiente en el monitor remoto.
5. Haz clic en la imagen del espejo para controlar la ventana. Si Windows no puede enfocar el original automáticamente, enfócalo en el origen y vuelve al espejo. La pérdida de foco pausa el control. **Esc** lo suelta. Puedes detener la transmisión cerrando el espejo o pulsando **Dejar de compartir** en el origen.

La conexión usa TCP 49731 para control y TCP 49732 para video. Ambos canales usan TLS 1.3. Se admite un espejo activo por origen. La captura conserva la ventana seleccionada y se pausa al minimizarla.

## Módulos

- `display/` consulta monitores, valida bordes e identifica el arrastre de ventanas.
- `capture/` captura la ventana seleccionada y mantiene el cuadro más reciente.
- `network/` transporta control y video. `pairing/` configura TLS.
- `input/` traduce eventos a Windows y comprueba el foco antes de inyectarlos.
- `ui/` contiene el mapa de pantallas, el emparejamiento y la ventana espejo.

Ejecuta las pruebas con `uv run python -m unittest discover -s tests`.
