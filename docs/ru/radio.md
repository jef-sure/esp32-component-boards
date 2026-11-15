# Радио рядом с чипом

У ESP32-P4 нет радио. На Guition JC1060P470C и JC8012P4A1C рядом с ним стоит ESP32-C6
на SDIO, и P4 пользуется её Wi-Fi и Bluetooth через esp_hosted: на C6 esp_hosted работает
сопроцессором, в программе — хостом. Версия esp_hosted у обеих сторон должна быть одна;
так говорит сам esp_hosted, а в новой версии есть исправления.

## Что приходит вместе с платой

- `espressif/esp_hosted` в диапазоне из `idf_component.yml` компонента и
  `espressif/esp_wifi_remote` на ESP-IDF ниже 6.1 (в 6.1 удалённый Wi-Fi есть в самом
  `esp_wifi`). Программа вызывает `esp_wifi_*`, как на чипе со своим радио.
- Настройки стороны хоста из данных платы: контроллер Bluetooth находится в C6, поэтому
  стек NimBLE программы обращается к нему через esp_hosted.
- `board_radio_start()`, см. [API](api.md): ждёт, пока C6 ответит, и пишет в лог, если на
  ней другая версия esp_hosted, чем у программы.
- Шаг прошивки, который приводит C6 к esp_hosted сборки.

## Прошивка C6

Прошивка C6 следует за esp_hosted, которую взяла сборка программы и запомнил
`dependencies.lock.<board>`: второй версии для выбора нет. Если программе нужна другая
esp_hosted, она называет её в своём `main/idf_component.yml` (см.
[версии](choosing-a-board.md#версии)), и C6 следует за ней.

На флеше платы прошивка C6 не хранится. Когда на C6 может быть другая версия, шаг
прошивки:

1. пишет на место приложения программы небольшую программу обновления вместе с
   загрузчиком и таблицей разделов самой программы, так что NVS и остальные разделы
   остаются;
2. спрашивает у C6 её версию через USB;
3. если версия другая, собирает образ C6 из той же esp_hosted, передаёт его по USB
   программе обновления, а та — в C6 по SDIO; после перезапуска C6 версия спрашивается
   ещё раз.

Затем прошивается сама программа и занимает своё место обратно. Программа обновления и
образ собираются только когда нужны, в `build/<board>/board_radio/`.

Измерено на JC1060P470C (ESP-IDF 6.1, esp_hosted 3.0.9 и 3.0.10, 2026-11-15): первая сборка
программы обновления занимает 18 с, образа — 21 с, повторная — 0,1 с; проверка без
обновления добавляет к прошивке около 9 с, обновление — около 19 с.

Найденная версия запоминается по MAC платы в
`$XDG_STATE_HOME/jef-sure-boards/radios.json` (`~/.local/state/...`). Пока программа просит
эту версию, шаг только читает MAC с USB чипа и ничего не стоит. Если C6 поменял кто-то
другой (другой компьютер, обновление из самой программы, esptool вручную), шаг этого не
увидит: об этом скажет лог `board_radio_start()`, а

```sh
BOARD_RADIO_FORCE=1 idf.py flash
```

проверит C6 заново.

### idf.py flash

Компонент добавляет свой шаг к цели `flash`; порт — тот, что назван в `idf.py -p`.
`ninja flash` без `ESPPORT` ничего не проверяет.

### Прошивка из VS Code

Расширение ESP-IDF прошивает esptool само, не через цель `flash`. Перед этим оно запускает
задачу pre-flash выбранной конфигурации, и `board_select.py` пишет её в пресет каждой
платы с таким радио:

```json
"vendor": {"espressif/vscode-esp-idf": {"settings": [{"type": "tasks", "value": {
    "preFlash": "cmake -E env ESPPORT=${config:idf.port} cmake --build ${config:idf.buildPath} --target board_radio"}}]}}
```

Расширение ждёт окончания задачи и не прошивает, если она завершилась с ошибкой.
Собственная задача pre-flash программы не заменяется; `board_select.py` тогда об этом
сообщает.

### Другая плата на порту

Тот же файл запоминает, какой платой прошивали каждое устройство. Сборка для другой платы
останавливается до того, как что-либо записано:

```
board_radio: the board on /dev/ttyACM1 (80:F1:B2:D3:3D:1B) was flashed as jc1060p470c from this computer,
and this build is for jc8012p4a1c: choose the board or the port of the build. BOARD_RADIO_FORCE=1 flashes it anyway.
```

Образ для другой ревизии чипа esptool не запишет и сам; эта проверка ловит платы на
одинаковом чипе.

### Более старая версия

Шаг записывает версию сборки и тогда, когда на C6 версия новее, и сообщает, откуда сборка
её взяла. Если в окружении указана копия реестра (см. [версии](choosing-a-board.md#версии)),
он называет и её:

```
board_radio: the radio of 80:F1:B2:D3:3D:1B runs esp_hosted 3.0.10, newer than 3.0.9, which the program has from
/…/clock/dependencies.lock.jc1060p470c: the step writes the older 3.0.9. The build was configured with
IDF_COMPONENT_LOCAL_STORAGE_URL=file:///…/.espressif/tools, and the component manager takes a version that fits from
that storage before the registry. To take the newest of the registry, remove dependencies.lock.jc1060p470c and run
idf.py reconfigure without the variable.
```

Проверено на JC1060P470C 2026-11-15: копия EIM от 2026-10-11 дала esp_hosted 3.0.9, а
lock, разрешённый заново без неё, — 3.0.10, которую шаг записал обратно.

## C6 со своей прошивкой

Плата, у которой на C6 другая прошивка (не esp_hosted программы), говорит об этом в
данных: `"firmware": {"set": "tool"}` у радио, в плате программы в
`components/local-boards/`, которая расширяет плату каталога. Тогда шаг прошивки ничего
не делает, а `board_radio_start()` только сообщает, что работает на C6.

Проверено на JC1060P470C с рукописными часами 2026-11-15: Wi-Fi и настройка сети по BLE
(NimBLE программы через esp_hosted) с C6, которую шаг привёл к 3.0.10.

## Чего пока нет

- Радио на SPI или UART: только SDIO.
