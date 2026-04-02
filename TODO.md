# TODO

## Planned Features

### Projector AR Overlay (HoloMat-style)
- Beamer projiziert auf eine Oberfläche, Kamera sieht die Szene
- Sprachbefehle wie "Male eine Box um die Maus" → Gemini erkennt Objekt → Canvas zeichnet Overlay
- **Kalibrierung:** Matte mit ArUco-Markern in den Ecken, OpenCV erkennt sie automatisch → `cv2.findHomography()` berechnet Kamera→Beamer-Mapping
- **Beamer-Canvas:** Zweites Browserfenster auf dem Beamer-Display, verbunden per Socket.IO
- **Referenz:** [HoloMat2](https://github.com/Concept-Bytes/HoloMat2) / [HoloMat v1](https://github.com/Concept-Bytes/Holomat) von Concept Bytes
- Benötigt: Kamera-Beamer-Kalibrierung, neues `project_overlay` Tool, Canvas-Komponente

### Wyoming Satellite / Raspberry Pi Integration
- Raspberry Pi mit Mic + Speaker als Thin Client
- Entweder Browser im Kiosk-Modus (`chromium --kiosk https://ada.server`)
- Oder headless Script das direkt per Socket Audio streamt
- Wyoming Protocol Bridge wäre nötig für HA Satellite1 Support

### Bambu Lab Printer Support
- X1C nutzt MQTT + Port 8883 (SSL), nicht HTTP wie OctoPrint/Moonraker
- Braucht MQTT Client mit TLS, Bambu-Protokoll, Access Code + Seriennummer
