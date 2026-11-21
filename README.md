# Floating Screens

Comparte ventanas y usa un solo mouse y teclado en dos PCs con Windows en la misma red.

## Conectar las PCs

1. Ejecuta `uv run floating-screens` en ambas PCs. Usa la misma versión en los dos equipos. Se requiere Windows 10 versión 1903 o posterior, Windows x64 y Python 3.13 con Tk y TLS-PSK.
2. En el destino, deja **Origen PC** desmarcado, pulsa **Activar recepción** y copia la **Security Key**. Cada activación genera una clave nueva. Autoriza el acceso en la red privada si Windows solicita permiso.
3. En el origen, marca **Origen PC** y pulsa **+ Añadir pantalla**. Introduce el nombre de red o IPv4 del destino y su clave.

## Compartir una ventana

En **Compartir ventana**, elige la PC y el monitor en los que quieres abrir el espejo. Arrastra la ventana por una zona libre de la barra de título y suéltala cuando la caja azul se ilumine. También puedes pulsar **Elegir ventana abierta…** y seleccionar una ventana de la lista. El espejo se abre en el monitor elegido y puedes moverlo y redimensionarlo. Puedes cerrarlo desde el destino o pulsar **Dejar de compartir** en el origen.

El espejo permite controlar la ventana original mientras ambas tienen el foco en sus respectivas PCs. Esa entrada se pausa cuando el origen controla el escritorio del destino por el borde.

## Cambiar el control por el borde

1. Selecciona una PC en el desplegable de destinos y pulsa **Configurar borde**. Elige el monitor local, uno de sus bordes libres y el monitor remoto donde debe entrar el puntero. Por ejemplo, **Derecha** en el origen conecta con la izquierda del monitor de destino.
2. Con **Cambiar PC por el borde** activado, mueve el puntero hasta el borde elegido. El mouse y el teclado pasan a controlar el escritorio del destino. Empuja el puntero de vuelta por el borde de entrada para regresar al origen, o pulsa **Ctrl+Alt+Esc**.
3. El texto del portapapeles se sincroniza en ambos sentidos mientras el control está en el destino. Se admiten hasta 12 KB de texto codificado. Imágenes y archivos quedan fuera del alcance actual.

La conexión usa TCP 49731 para control y TCP 49732 para video, ambos con TLS 1.3. Se admite un espejo y un cambio de control activos a la vez por origen.

## Módulos

- `display/` consulta monitores, valida bordes e identifica el arrastre de ventanas.
- `capture/` captura la ventana seleccionada y mantiene el cuadro más reciente.
- `network/` transporta control y video. `pairing/` configura TLS.
- `input/` coordina el control por el borde, el portapapeles y la entrada del espejo.
- `ui/` contiene la caja de ventanas, el mapa de pantallas y el espejo.

Ejecuta las pruebas con `uv run python -m unittest discover -s tests`.
