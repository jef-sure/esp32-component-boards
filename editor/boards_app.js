/*
 * The boards editor: one board as data, the way the README says it — its buses a named
   registry (a name claims the chip's host), its devices referencing a bus and carrying their
   own strobes. Vue and Pinia from a CDN, no build step (the way of hw-fonts); what it saves
   is what tools/boards_gen.py reads. The checks are the store's (boards_store.js).
*/
var app = VueDemi.createApp({
    template: `
    <div class="container-fluid py-3">
        <div class="row mb-2">
            <div class="col">
                <h3>boards editor</h3>
                <p class="text-muted mb-0">One board, as data: this edits the JSON that is the only source of truth —
                <code>tools/boards_gen.py</code> makes the glue, <code>tools/check_boards.py</code> checks the two agree.
                Save as <code>board.json</code> into <code>boards-data/&lt;board&gt;/</code>.</p>
            </div>
        </div>
        <div class="row mb-3 align-items-end">
            <div class="col-md-4">
                <label class="form-label mb-1">open a board.json</label>
                <input type="file" class="form-control" @change="store.load($event.target.files[0])">
                <div v-if="store.uploadError" class="alert alert-danger mt-2 py-2 mb-0">{{ store.uploadError }}</div>
            </div>
            <div class="col-auto"><button class="btn btn-outline-secondary" @click="store.newBoard()">new board</button></div>
            <div class="col-auto"><button class="btn btn-primary" :disabled="store.problems.length" @click="store.save()">Save board.json</button></div>
        </div>
        <div v-if="store.problems.length" class="alert alert-warning py-2">
            <div v-for="p in store.problems" :key="p">{{ p }}</div>
        </div>

        <div class="row">
            <div class="col-lg-6">
                <h5>The board</h5>
                <div class="row g-2 mb-2">
                    <div class="col-md-4"><label class="form-label mb-0">name</label>
                        <input class="form-control" v-model="store.board.name"></div>
                    <div class="col-md-8"><label class="form-label mb-0">title</label>
                        <input class="form-control" v-model="store.board.title"></div>
                </div>
                <div class="mb-2"><label class="form-label mb-0">description</label>
                    <input class="form-control" v-model="store.board.description"></div>
                <div class="row g-2 mb-2">
                    <div class="col-md-4"><label class="form-label mb-0">target</label>
                        <select class="form-select" :disabled="!!store.board.module" v-model="store.board.mcu.target">
                            <option>esp32</option><option>esp32s3</option><option>esp32p4</option>
                        </select></div>
                    <div class="col-md-4"><label class="form-label mb-0">flash, MB</label>
                        <input type="number" class="form-control" v-model.number="store.board.mcu.flash_mb"></div>
                    <div class="col-md-4"><label class="form-label mb-0">PSRAM, MB</label>
                        <input type="number" class="form-control" v-model.number="store.board.mcu.psram_mb"></div>
                </div>
                <div class="mb-2"><label class="form-label mb-0">notes of the chip</label>
                    <input class="form-control" v-model="store.board.mcu.notes" placeholder="a rev-3 chip wants PSRAM at 250 MHz — the reasons the sdkconfig.defaults carries"></div>
                <div class="form-check form-switch mb-3">
                    <input class="form-check-input" type="checkbox" id="isModule" v-model="store.board.module">
                    <label class="form-label mb-0" for="isModule">a module, not a board: rides the carrier's buses, no MCU of its own</label>
                </div>

                <h5>Buses</h5>
                <p class="text-muted small mb-2">A name a bus, its pins and its speed its own; the name claims the
                chip's host or port ("spi2" is SPI2, "i2c0" is the chip's I2C). A device references a bus and carries
                its own strobes — two devices on one bus is two entries. A kind the component sets not up itself is
                kept as data (<code>board_bus_get</code>): every value a pin, a number or a word.</p>
                <div v-for="group in store.busGroups" :key="group.kind" class="mb-3">
                    <div class="d-flex justify-content-between">
                        <h6 class="mb-1">{{ group.title }} <span class="text-muted small">{{ group.known ? '' : '— kept as data' }}</span></h6>
                    </div>
                    <div v-for="b in group.buses" :key="b.name" class="input-group input-group-sm mb-1">
                        <span class="input-group-text" style="min-width: 7em">{{ b.name }}</span>
                        <template v-if="group.known">
                            <template v-for="(mode, field) in busKinds[group.kind].fields" :key="field">
                                <span v-if="mode !== 'opt'" class="input-group-text">{{ field }}</span>
                                <input v-if="mode !== 'opt'" type="number" class="form-control" style="max-width: 6em"
                                    v-model.number="b.bus[field]">
                            </template>
                        </template>
                        <template v-else>
                            <span class="input-group-text">fields</span>
                            <input class="form-control" :value="busExtra(b.bus)" @change="setBusExtra(b.bus, $event.target.value)"
                                placeholder="clk=18 cmd=19 d0=14 … a pin, a number or a word each">
                        </template>
                        <button class="btn btn-outline-danger" @click="store.removeBus(group.kind, b.own)">&times;</button>
                    </div>
                </div>
                <div class="input-group input-group-sm mb-3">
                    <select class="form-select" v-model="newBusKind">
                        <option v-for="(spec, kind) in busKinds" :key="kind" :value="kind">{{ spec.title }} — {{ spec.own }}</option>
                        <option value="other">other — kept as data (sdio, uart, …)</option>
                    </select>
                    <input class="form-control" v-model="newBusOwn" :placeholder="busKinds[newBusKind] ? busKinds[newBusKind].own.split(': ')[1] : 'the kind, sdio'">
                    <button class="btn btn-outline-success" @click="addBus">add</button>
                </div>

                <h5>Button &nbsp;·&nbsp; SD slot</h5>
                <div class="row g-2 mb-2">
                    <div class="col-auto"><div class="form-check form-switch mt-2">
                        <input class="form-check-input" type="checkbox" id="hasButton" :checked="!!store.board.button"
                            @change="store.board.button = $event.target.checked ? { pin: 0, active_low: true } : null">
                        <label class="form-label mb-0" for="hasButton">button</label>
                    </div></div>
                    <div class="col-md-3" v-if="store.board.button"><label class="form-label mb-0">pin</label>
                        <input type="number" class="form-control" v-model.number="store.board.button.pin"></div>
                    <div class="col-auto" v-if="store.board.button"><div class="form-check mt-2">
                        <input class="form-check-input" type="checkbox" id="btnActive" v-model="store.board.button.active_low">
                        <label class="form-label mb-0" for="btnActive">active low</label>
                    </div></div>
                </div>
                <div class="row g-2 mb-3">
                    <div class="col-auto"><div class="form-check form-switch mt-2">
                        <input class="form-check-input" type="checkbox" id="hasSd" :checked="!!store.board.sd"
                            @change="store.board.sd = $event.target.checked ? { bus: (store.busNamesOf(['spi'])[0] || 'spi.spi2'), cs: 5 } : null">
                        <label class="form-label mb-0" for="hasSd">SD slot</label>
                    </div></div>
                    <div class="col-md-4" v-if="store.board.sd"><label class="form-label mb-0">bus</label>
                        <select class="form-select" v-model="store.board.sd.bus">
                            <option v-for="n in store.busNamesOf(['spi'])" :key="n">{{ n }}</option>
                        </select></div>
                    <div class="col-md-3" v-if="store.board.sd"><label class="form-label mb-0">cs</label>
                        <input type="number" class="form-control" v-model.number="store.board.sd.cs"></div>
                </div>
            </div>

            <div class="col-lg-6">
                <h5>Display</h5>
                <div class="form-check form-switch mb-2">
                    <input class="form-check-input" type="checkbox" id="hasDisplay" :checked="!!store.board.display"
                        @change="store.board.display = $event.target.checked ? newDisplay() : null">
                    <label class="form-label mb-0" for="hasDisplay">this board has a display</label>
                </div>
                <template v-if="store.board.display">
                    <div class="row g-2 mb-2">
                        <div class="col-md-4"><label class="form-label mb-0">family</label>
                            <select class="form-select" v-model="displayFamily" @change="familyChanged">
                                <option value="pixel">a pixel panel (dgx)</option>
                                <option value="character">a character LCD (hd44780)</option>
                            </select></div>
                        <div class="col-md-4" v-if="displayFamily === 'pixel'"><label class="form-label mb-0">driver</label>
                            <select class="form-select" v-model="store.board.display.driver">
                                <option v-for="(depths, drv) in panelDrivers" :key="drv">{{ drv }}</option>
                            </select></div>
                        <div class="col-md-4" v-if="displayFamily === 'character'"><label class="form-label mb-0">driver</label>
                            <select class="form-select" v-model="store.board.display.driver">
                                <option v-for="(geoms, drv) in characterDrivers" :key="drv">{{ drv }}</option>
                            </select></div>
                        <div class="col-md-4" v-if="displayFamily === 'character'"><label class="form-label mb-0">geometry</label>
                            <select class="form-select" v-model="store.board.display.geometry">
                                <option v-for="g in characterDrivers[store.board.display.driver] || []" :key="g">{{ g }}</option>
                            </select></div>
                    </div>
                    <template v-if="displayFamily === 'pixel'">
                        <div class="row g-2 mb-2">
                            <div class="col-md-4"><label class="form-label mb-0">bus</label>
                                <select class="form-select" v-model="store.board.display.bus.bus" @change="displayBusChanged">
                                    <option v-for="n in store.busNamesOf(['spi', 'qspi', 'dsi', 'p8'])" :key="n">{{ n }}</option>
                                </select></div>
                            <div class="col-md-4"><label class="form-label mb-0">depth, bits</label>
                                <select class="form-select" v-model.number="store.board.display.depth_bits">
                                    <option v-for="d in panelDrivers[store.board.display.driver] || []" :key="d" :value="d">{{ d }}</option>
                                </select></div>
                            <div class="col-md-4"><label class="form-label mb-0">backlight</label>
                                <input type="number" class="form-control" v-model.number="store.board.display.backlight"></div>
                        </div>
                        <div class="row g-2 mb-2">
                            <div class="col" v-for="line in panelStrobes[busKindOf(store.board.display.bus.bus)]" :key="line">
                                <label class="form-label mb-0">{{ line }}</label>
                                <input type="number" class="form-control" v-model.number="store.board.display.bus[line]">
                            </div>
                            <div class="col"><label class="form-label mb-0">rst</label>
                                <input type="number" class="form-control" v-model.number="store.board.display.rst"></div>
                        </div>
                        <div class="row g-2 mb-2">
                            <div class="col-md-3"><label class="form-label mb-0">width, px</label>
                                <input type="number" class="form-control" v-model.number="store.board.display.panel.width"></div>
                            <div class="col-md-3"><label class="form-label mb-0">height, px</label>
                                <input type="number" class="form-control" v-model.number="store.board.display.panel.height"></div>
                            <div class="col-md-3"><label class="form-label mb-0">width, mm</label>
                                <input type="number" class="form-control" v-model.number="store.board.display.panel.mm_w"></div>
                            <div class="col-md-3"><label class="form-label mb-0">height, mm</label>
                                <input type="number" class="form-control" v-model.number="store.board.display.panel.mm_h"></div>
                        </div>
                        <p class="text-muted small mb-2">The panel is the glass as the controller scans it — pixels and
                        millimetres one way; the orientation below turns it into the way the board shows it.</p>
                        <div class="row g-2 mb-3">
                            <div class="col-md-4"><label class="form-label mb-0">x as scanned</label>
                                <select class="form-select" v-model="store.board.display.original_orientation.x">
                                    <option>left-right</option><option>right-left</option>
                                </select></div>
                            <div class="col-md-4"><label class="form-label mb-0">y as scanned</label>
                                <select class="form-select" v-model="store.board.display.original_orientation.y">
                                    <option>top-bottom</option><option>bottom-top</option>
                                </select></div>
                            <div class="col-md-4"><div class="form-check mt-2">
                                <input class="form-check-input" type="checkbox" id="orientSwap" v-model="store.board.display.original_orientation.swap">
                                <label class="form-label mb-0" for="orientSwap">lies swapped (landscape)</label>
                            </div></div>
                        </div>
                    </template>
                    <template v-else>
                        <div class="row g-2 mb-3">
                            <div class="col-md-4"><label class="form-label mb-0">transport</label>
                                <select class="form-select" v-model="store.board.display.bus.bus">
                                    <option value="i2c.i2c0">I2C — a PCF8574 backpack</option>
                                    <option value="gpio.4bit">GPIO 4-bit</option>
                                    <option value="gpio.8bit">GPIO 8-bit</option>
                                </select></div>
                            <div class="col-md-4" v-if="characterOnI2c"><label class="form-label mb-0">address</label>
                                <input class="form-control" v-model="store.board.display.bus.address" placeholder="0x27"></div>
                            <div class="col-md-8" v-if="!characterOnI2c"><label class="form-label mb-0">pins</label>
                                <input class="form-control" :value="busExtra(store.board.display.bus.pins || {})"
                                    @change="setBusExtra(store.board.display.bus.pins || (store.board.display.bus.pins = {}), $event.target.value)"
                                    placeholder="rs=2 en=15 d4=19 …"></div>
                        </div>
                    </template>
                </template>

                <h5>Touch</h5>
                <div class="form-check form-switch mb-2">
                    <input class="form-check-input" type="checkbox" id="hasTouch" :checked="!!store.board.touch"
                        @change="store.board.touch = $event.target.checked ? newTouch() : null">
                    <label class="form-label mb-0" for="hasTouch">this board has a touch panel</label>
                </div>
                <template v-if="store.board.touch">
                    <div class="row g-2 mb-2">
                        <div class="col-md-4"><label class="form-label mb-0">kind</label>
                            <select class="form-select" v-model="store.board.touch.kind" @change="touchKindChanged">
                                <option value="gt911">gt911 — I2C</option>
                                <option value="gsl3680">gsl3680 — I2C</option>
                                <option value="esp_lcd_touch">any esp_lcd_touch driver — SPI</option>
                            </select></div>
                        <div class="col-md-4"><label class="form-label mb-0">bus</label>
                            <select class="form-select" v-model="store.board.touch.bus">
                                <option v-for="n in store.busNamesOf(touchKindsOf())" :key="n">{{ n }}</option>
                            </select></div>
                        <div class="col-md-4" v-if="store.board.touch.kind === 'esp_lcd_touch'"><label class="form-label mb-0">cs</label>
                            <input type="number" class="form-control" v-model.number="store.board.touch.cs"></div>
                    </div>
                    <div class="row g-2 mb-2" v-if="store.board.touch.kind === 'esp_lcd_touch'">
                        <div class="col-md-5"><label class="form-label mb-0">component (namespace/name in the registry)</label>
                            <input class="form-control" v-model="store.board.touch.component" placeholder="atanisoft/esp_lcd_touch_xpt2046"></div>
                        <div class="col-md-3"><label class="form-label mb-0">header</label>
                            <input class="form-control" v-model="store.board.touch.header" placeholder="esp_lcd_touch_xpt2046.h"></div>
                        <div class="col-md-2"><label class="form-label mb-0">irq</label>
                            <input type="number" class="form-control" v-model.number="store.board.touch.irq"></div>
                        <div class="col-md-2"><label class="form-label mb-0">hz</label>
                            <input type="number" class="form-control" v-model.number="store.board.touch.hz"></div>
                    </div>
                    <div class="row g-2 mb-3">
                        <div class="col-md-3"><label class="form-label mb-0">fingers</label>
                            <input type="number" class="form-control" v-model.number="store.board.touch.fingers"></div>
                        <div class="col-md-3"><label class="form-label mb-0">x_max</label>
                            <input type="number" class="form-control" v-model.number="store.board.touch.x_max"></div>
                        <div class="col-md-3"><label class="form-label mb-0">y_max</label>
                            <input type="number" class="form-control" v-model.number="store.board.touch.y_max"></div>
                        <div class="col-md-3" v-if="store.board.touch.kind !== 'esp_lcd_touch'"><label class="form-label mb-0">rst / int</label>
                            <div class="input-group">
                                <input type="number" class="form-control" v-model.number="store.board.touch.rst">
                                <input type="number" class="form-control" v-model.number="store.board.touch.int">
                            </div></div>
                    </div>

                    <h6>Calibration</h6>
                    <p class="text-muted small mb-1">Measure the board (<code>dgx_di_calibrate_measure</code>), paste
                    what it prints — the C initializer of <code>dgx_di_calibration_t</code>.</p>
                    <textarea class="form-control font-monospace" rows="5" v-model="store.calibrationPaste"
                        placeholder="{.version = 1, .size = sizeof(dgx_di_calibration_t), .x_min = 0, …}"></textarea>
                    <div class="d-flex align-items-center mt-1 mb-1">
                        <button class="btn btn-outline-primary btn-sm" @click="store.applyCalibration()">apply the paste</button>
                        <span v-if="store.calibrationNote" class="text-muted small ms-2">{{ store.calibrationNote }}</span>
                        <span v-if="store.calibrationError" class="text-danger small ms-2">{{ store.calibrationError }}</span>
                        <span v-else-if="store.board.touch.calibration" class="text-success small ms-2">in the data ✓</span>
                    </div>
                    <div class="form-check mb-3" v-if="store.board.touch.calibration">
                        <input class="form-check-input" type="checkbox" id="calMeasured"
                            :checked="store.board.touch.calibration.measured !== false"
                            @change="store.board.touch.calibration.measured = $event.target.checked">
                        <label class="form-label mb-0" for="calMeasured">measured on a board (unchecked: a placeholder, the glue warns at start and the README says so)</label>
                    </div>
                </template>

                <h5>Sound</h5>
                <div class="form-check form-switch mb-2">
                    <input class="form-check-input" type="checkbox" id="hasSound" :checked="!!store.board.sound"
                        @change="store.board.sound = $event.target.checked ? newSound() : null">
                    <label class="form-label mb-0" for="hasSound">this board has sound</label>
                </div>
                <template v-if="store.board.sound">
                    <div class="row g-2 mb-2">
                        <div class="col-md-4"><label class="form-label mb-0">kind</label>
                            <select class="form-select" v-model="store.board.sound.kind" @change="soundKindChanged">
                                <option value="es8311">es8311 — a codec on I2C and I2S</option>
                                <option value="dac">dac — the chip's own, on a pin</option>
                            </select></div>
                        <div class="col-md-4"><label class="form-label mb-0">sample rate</label>
                            <input type="number" class="form-control" v-model.number="store.board.sound.sample_rate"></div>
                        <div class="col-md-4" v-if="store.board.sound.kind === 'es8311'"><label class="form-label mb-0">volume, 0..100</label>
                            <input type="number" class="form-control" v-model.number="store.board.sound.volume"></div>
                    </div>
                    <div class="row g-2 mb-3" v-if="store.board.sound.kind === 'es8311'">
                        <div class="col-md-4"><label class="form-label mb-0">I2C bus</label>
                            <select class="form-select" v-model="store.board.sound.bus">
                                <option v-for="n in store.busNamesOf(['i2c'])" :key="n">{{ n }}</option>
                            </select></div>
                        <div class="col-md-4"><label class="form-label mb-0">address</label>
                            <input class="form-control" v-model="store.board.sound.address" placeholder="0x18"></div>
                        <div class="col-md-4"><label class="form-label mb-0">I2S bus</label>
                            <select class="form-select" v-model="store.board.sound.i2s_bus">
                                <option v-for="n in store.busNamesOf(['i2s'])" :key="n">{{ n }}</option>
                            </select></div>
                    </div>
                    <div class="row g-2 mb-3" v-else>
                        <div class="col-md-4"><label class="form-label mb-0">out pin (the ESP32's DAC)</label>
                            <select class="form-select" v-model.number="store.board.sound.out">
                                <option :value="25">25 (channel 0)</option><option :value="26">26 (channel 1)</option>
                            </select></div>
                        <div class="col-md-4"><label class="form-label mb-0">amplifier enable pin (empty: none)</label>
                            <input type="number" class="form-control" :value="store.board.sound.pa"
                                @change="store.board.sound.pa = $event.target.value === '' ? null : parseInt($event.target.value, 10)"></div>
                    </div>
                </template>
            </div>
        </div>
    </div>
`,
    setup() {
        const store = useBoardStore();
        const newBusKind = Vue.ref('spi');
        const newBusOwn = Vue.ref('');
        const displayFamily = Vue.ref(familyOf(store.board.display));
        function familyOf(d) {
            return d && d.geometry ? 'character' : 'pixel';
        }
        function newDisplay() {
            return { driver: 'jd9165', bus: { bus: '', cs: null, dc: null }, panel: { width: 1024, height: 600, mm_w: 154, mm_h: 86 },
                     depth_bits: 16, backlight: null, rst: null, backlight_on_high: true,
                     original_orientation: { x: 'left-right', y: 'top-bottom', swap: false } };
        }
        function newTouch() {
            return { kind: 'gt911', bus: '', x_max: 1023, y_max: 599, fingers: 5, rst: null, int: null, calibration: null };
        }
        function newSound() {
            return { kind: 'es8311', bus: '', address: '0x18', sample_rate: 22050, volume: 25, pa: null, i2s_bus: '' };
        }
        function busKindOf(name) {
            return String(name || '').split('.')[0];
        }
        function touchKindsOf() {
            return store.board.touch && store.board.touch.kind === 'esp_lcd_touch' ? ['spi'] : ['i2c'];
        }
        function addBus() {
            if (newBusKind.value === 'other') {
                const kind = (newBusOwn.value.split('.')[0] || '').trim();
                const own = (newBusOwn.value.split('.')[1] || '').trim();
                store.addBus(kind, own);
            } else {
                store.addBus(newBusKind.value, newBusOwn.value.trim());
            }
            newBusOwn.value = '';
        }
        function familyChanged() {
            const d = store.board.display;
            if (displayFamily.value === 'character') {
                store.board.display = { driver: 'hd44780', geometry: '20x4', bus: { bus: 'i2c.i2c0', address: '0x27' } };
            } else {
                store.board.display = newDisplay();
            }
        }
        function displayBusChanged() {
            const d = store.board.display;
            const kind = busKindOf(d.bus.bus);
            d.bus.cs = kind === 'dsi' ? null : d.bus.cs;
        }
        function touchKindChanged() {
            const t = store.board.touch;
            const names = store.busNamesOf(t.kind === 'esp_lcd_touch' ? ['spi'] : ['i2c']);
            t.bus = names[0] || '';
            if (t.kind === 'esp_lcd_touch') {
                t.cs = t.cs == null ? 33 : t.cs; t.irq = t.irq == null ? 36 : t.irq; t.fingers = 1; t.resistive = true; t.hz = 1000000;
                t.component = t.component || 'atanisoft/esp_lcd_touch_xpt2046'; t.header = t.header || 'esp_lcd_touch_xpt2046.h';
                t.x_max = 4095; t.y_max = 4095;
            } else { delete t.component; delete t.header; delete t.cs; delete t.irq; delete t.hz; delete t.resistive; t.fingers = 5; }
        }
        function soundKindChanged() {
            const s = store.board.sound;
            if (s.kind === 'dac') store.board.sound = { kind: 'dac', out: 26, pa: null, sample_rate: s.sample_rate };
            else store.board.sound = newSound();
        }
        /* the fields of a bus the component sets not up itself: one line, k=v — a pin, a
           number or a word each; parsed back into the bus's own object */
        function busExtra(obj) {
            return Object.entries(obj).filter(([k, v]) => v !== null).map(([k, v]) => `${k}=${v}`).join(' ');
        }
        function setBusExtra(obj, text) {
            for (const k of Object.keys(obj)) delete obj[k];
            for (const pair of text.split(/\s+/)) {
                const [k, v] = pair.split('=');
                if (!k) continue;
                const n = parseInt(v, 10);
                obj[k] = /^-?\d+$/.test(v) ? n : v;
            }
        }
        Vue.watch(() => store.board.display && store.board.display.driver, () => {
            if (displayFamily.value === 'pixel' && store.board.display && !PanelDrivers[store.board.display.driver]) return;
            const depths = store.board.display && PanelDrivers[store.board.display.driver];
            if (depths && !depths.includes(store.board.display.depth_bits)) store.board.display.depth_bits = depths[0];
        });
        return { store, panelDrivers: PanelDrivers, characterDrivers: CharacterDrivers, busKinds: BusKinds, panelStrobes: PanelStrobes,
                 newBusKind, newBusOwn, displayFamily, newDisplay, newTouch, newSound, familyOf, busKindOf, touchKindsOf,
                 addBus, familyChanged, displayBusChanged, touchKindChanged, soundKindChanged, busExtra, setBusExtra };
    }
});
app.use(Pinia.createPinia());
app.mount('#vue-app');
