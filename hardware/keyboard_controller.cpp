// =============================================================================
//  Gesture MIDI Controller — Physical Hardware Interface
//
//  Handles the wired peripherals on the Raspberry Pi 4B:
//    - 12 momentary keys  -> MIDI notes (one chromatic octave)
//    - 2 tactile buttons  -> toggle two programmable modes/tones
//    - 2 PWM LEDs         -> indicate each mode's active state
//    - 16x2 I2C LCD       -> shows the current gesture effect + intensity
//
//  MIDI is emitted on an ALSA sequencer port ("PiKeyboard") which is
//  auto-connected to the USB MIDI gadget (f_midi), so these keys join the
//  same MIDI stream the gesture engine sends on.
//
//  Bridge to the Python gesture system (decoupled, file-based):
//    READS  /tmp/pi_to_hw_lcd   : up to 2 lines -> shown on the LCD
//                                 (Python writes effect name + intensity here)
//    WRITES /tmp/hw_buttons     : "b1=<0|1> b2=<0|1>" whenever a button toggles
//                                 (Python can read which physical mode is active)
//
//  ---------------------------------------------------------------------------
//  BUILD (on the Pi):
//      sudo apt install -y pigpio libpigpio-dev libasound2-dev
//      make                       # or see the compile line below
//
//      g++ -std=c++17 -O2 keyboard_controller.cpp -o keyboard_controller \
//          -lpigpio -lasound -lrt -lpthread
//
//  RUN (pigpio needs root for direct register access):
//      sudo ./keyboard_controller
//
//  pigpio works on Pi 4B; it is NOT compatible with the Pi 5.
// =============================================================================

#include <pigpio.h>
#include <alsa/asoundlib.h>

#include <atomic>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <csignal>
#include <fstream>
#include <mutex>
#include <string>
#include <unistd.h>

// ----------------------------------------------------------------------------
// Pin allocation (BCM GPIO numbers)
// ----------------------------------------------------------------------------
// 12 keys, in playing order: Key1 (lowest) .. Key12 (highest).
static const int KEY_GPIO[12] = {
    21,  // Key 1  C  - Pin 40
    26,  // Key 2  C# - Pin 37
    20,  // Key 3  D  - Pin 38
    19,  // Key 4  D# - Pin 35
    16,  // Key 5  E  - Pin 36
     0,  // Key 6  F  - Pin 27  (I2C0 SDA — OK if no HAT EEPROM)
     6,  // Key 7  F# - Pin 31
    11,  // Key 8  G  - Pin 23
    12,  // Key 9  G# - Pin 32
     9,  // Key 10 A  - Pin 21
    10,  // Key 11 A# - Pin 19
     1,  // Key 12 B  - Pin 28  (I2C0 SCL — OK if no HAT EEPROM)
};

static const int BUTTON1_GPIO = 17;   // Pin 11
static const int BUTTON2_GPIO = 27;   // Pin 13

static const int LED1_GPIO = 18;      // Pin 12 (hardware PWM0)
static const int LED2_GPIO = 13;      // Pin 33 (hardware PWM1)

// LCD is on the primary I2C bus: SDA=GPIO2 (Pin 3), SCL=GPIO3 (Pin 5).
static const int  I2C_BUS      = 1;
static const int  LCD_ADDR     = 0x27;   // common PCF8574 backpack addr (try 0x3F)
static const int  LCD_COLS     = 16;
static const int  LCD_ROWS     = 2;

// ----------------------------------------------------------------------------
// MIDI configuration
// ----------------------------------------------------------------------------
static const int  MIDI_CHANNEL   = 0;     // 0-15
static const int  BASE_NOTE      = 60;    // Key 1 = middle C (C4)
static const int  KEY_VELOCITY   = 100;

// LED wiring: true if the LED lights when the GPIO is driven LOW
// (cathode -> GPIO through the series resistor, anode -> 3V3). This rig is
// active-low for everything, so leave this true.
static const bool LED_ACTIVE_LOW = true;

// LED brightness (pigpio hardware PWM duty cycle is 0..1,000,000 = fraction of
// time the pin is HIGH). LED_ON_DUTY is expressed as "how lit" regardless of
// polarity; led_set() inverts it for active-low wiring.
static const int  LED_PWM_FREQ   = 800;
static const int  LED_ON_DUTY    = 600000;   // ~60% — comfortable brightness
static const int  LED_OFF_DUTY   = 0;

// File bridge to the Python gesture system.
static const char* LCD_INPUT_FILE   = "/tmp/pi_to_hw_lcd";
static const char* BUTTON_OUT_FILE  = "/tmp/hw_buttons";

// ----------------------------------------------------------------------------
// Globals
// ----------------------------------------------------------------------------
static volatile std::sig_atomic_t g_running = 1;

static snd_seq_t* g_seq    = nullptr;
static int        g_seqPort = -1;
static std::mutex g_midiMutex;

static int             g_lcdHandle = -1;
static std::mutex      g_lcdMutex;

static std::atomic<bool> g_mode1{false};   // toggled by Button 1
static std::atomic<bool> g_mode2{false};   // toggled by Button 2

// ============================================================================
//  LCD: HD44780 driven through a PCF8574 I2C expander (4-bit mode)
//  PCF8574 bit map: P0=RS, P1=RW, P2=EN, P3=Backlight, P4..P7=D4..D7
// ============================================================================
static const uint8_t LCD_RS = 0x01;
static const uint8_t LCD_EN = 0x04;
static const uint8_t LCD_BL = 0x08;   // backlight on

static void pcf_write(uint8_t data) {
    i2cWriteByte(g_lcdHandle, data | LCD_BL);
}

static void lcd_pulse(uint8_t data) {
    pcf_write(data | LCD_EN);
    usleep(1);
    pcf_write(data & ~LCD_EN);
    usleep(50);
}

// Send one byte as two 4-bit nibbles. mode = LCD_RS for data, 0 for command.
static void lcd_send(uint8_t value, uint8_t mode) {
    uint8_t hi = (value & 0xF0) | mode;
    uint8_t lo = ((value << 4) & 0xF0) | mode;
    lcd_pulse(hi);
    lcd_pulse(lo);
}

static void lcd_cmd(uint8_t c)  { lcd_send(c, 0); }
static void lcd_char(uint8_t c) { lcd_send(c, LCD_RS); }

static bool lcd_init() {
    g_lcdHandle = i2cOpen(I2C_BUS, LCD_ADDR, 0);
    if (g_lcdHandle < 0) {
        fprintf(stderr, "LCD: i2cOpen failed at addr 0x%02X (try 0x3F)\n", LCD_ADDR);
        return false;
    }
    usleep(50000);
    // Standard 4-bit initialisation sequence.
    lcd_send(0x33, 0); usleep(5000);
    lcd_send(0x32, 0); usleep(5000);
    lcd_cmd(0x28);   // 4-bit, 2 lines, 5x8 font
    lcd_cmd(0x0C);   // display on, cursor off, blink off
    lcd_cmd(0x06);   // entry mode: increment, no shift
    lcd_cmd(0x01);   // clear
    usleep(2000);
    return true;
}

static void lcd_set_cursor(int col, int row) {
    static const uint8_t row_off[4] = {0x00, 0x40, 0x14, 0x54};
    if (row < 0 || row >= LCD_ROWS) row = 0;
    lcd_cmd(0x80 | (row_off[row] + col));
}

// Write a string to a row, padded/truncated to LCD_COLS.
static void lcd_write_line(int row, const std::string& text) {
    std::lock_guard<std::mutex> lock(g_lcdMutex);
    if (g_lcdHandle < 0) return;
    lcd_set_cursor(0, row);
    for (int i = 0; i < LCD_COLS; ++i)
        lcd_char(i < (int)text.size() ? (uint8_t)text[i] : ' ');
}

// ============================================================================
//  MIDI via ALSA sequencer
// ============================================================================
static bool midi_init() {
    if (snd_seq_open(&g_seq, "default", SND_SEQ_OPEN_OUTPUT, 0) < 0) {
        fprintf(stderr, "MIDI: cannot open ALSA sequencer\n");
        return false;
    }
    snd_seq_set_client_name(g_seq, "PiKeyboard");
    g_seqPort = snd_seq_create_simple_port(
        g_seq, "out",
        SND_SEQ_PORT_CAP_READ | SND_SEQ_PORT_CAP_SUBS_READ,
        SND_SEQ_PORT_TYPE_MIDI_GENERIC | SND_SEQ_PORT_TYPE_APPLICATION);
    if (g_seqPort < 0) {
        fprintf(stderr, "MIDI: cannot create port\n");
        return false;
    }
    return true;
}

// Find a client/port whose name contains "f_midi" and connect to it.
static void midi_autoconnect() {
    snd_seq_client_info_t* cinfo;
    snd_seq_port_info_t*   pinfo;
    snd_seq_client_info_alloca(&cinfo);
    snd_seq_port_info_alloca(&pinfo);

    snd_seq_client_info_set_client(cinfo, -1);
    while (snd_seq_query_next_client(g_seq, cinfo) >= 0) {
        int client = snd_seq_client_info_get_client(cinfo);
        const char* cname = snd_seq_client_info_get_name(cinfo);
        snd_seq_port_info_set_client(pinfo, client);
        snd_seq_port_info_set_port(pinfo, -1);
        while (snd_seq_query_next_port(g_seq, pinfo) >= 0) {
            unsigned int caps = snd_seq_port_info_get_capability(pinfo);
            if (!(caps & SND_SEQ_PORT_CAP_WRITE)) continue;
            if (cname && strstr(cname, "f_midi")) {
                int port = snd_seq_port_info_get_port(pinfo);
                if (snd_seq_connect_to(g_seq, g_seqPort, client, port) == 0)
                    printf("MIDI: connected PiKeyboard -> %s (%d:%d)\n",
                           cname, client, port);
                return;
            }
        }
    }
    printf("MIDI: f_midi gadget not found yet — connect later with:\n"
           "      aconnect PiKeyboard f_midi\n");
}

static void midi_send_note(int note, bool on) {
    std::lock_guard<std::mutex> lock(g_midiMutex);
    if (!g_seq) return;
    snd_seq_event_t ev;
    snd_seq_ev_clear(&ev);
    snd_seq_ev_set_source(&ev, g_seqPort);
    snd_seq_ev_set_subs(&ev);
    snd_seq_ev_set_direct(&ev);
    if (on)  snd_seq_ev_set_noteon(&ev,  MIDI_CHANNEL, note, KEY_VELOCITY);
    else     snd_seq_ev_set_noteoff(&ev, MIDI_CHANNEL, note, 0);
    snd_seq_event_output(g_seq, &ev);
    snd_seq_drain_output(g_seq);
}

// ============================================================================
//  LEDs
// ============================================================================
static void led_set(int gpio, bool on) {
    int duty = on ? LED_ON_DUTY : LED_OFF_DUTY;   // duty = fraction of time HIGH
    if (LED_ACTIVE_LOW) duty = 1000000 - duty;    // LOW lights the LED -> invert
    gpioHardwarePWM(gpio, LED_PWM_FREQ, duty);
}

// ============================================================================
//  Button -> Python bridge
// ============================================================================
static void write_button_state() {
    std::ofstream f(BUTTON_OUT_FILE, std::ios::trunc);
    if (f) f << "b1=" << (g_mode1 ? 1 : 0)
             << " b2=" << (g_mode2 ? 1 : 0) << "\n";
}

// ============================================================================
//  GPIO edge callback (runs in a pigpio thread)
//  Keys/buttons are wired active-low (to GND) with internal pull-ups,
//  so level==0 means pressed, level==1 means released.
// ============================================================================
static void gpio_callback(int gpio, int level, uint32_t /*tick*/) {
    if (level == PI_TIMEOUT) return;   // watchdog, ignore
    bool pressed = (level == 0);

    // Keys
    for (int i = 0; i < 12; ++i) {
        if (gpio == KEY_GPIO[i]) {
            midi_send_note(BASE_NOTE + i, pressed);
            return;
        }
    }

    // Buttons toggle on press (falling edge) only.
    if (gpio == BUTTON1_GPIO && pressed) {
        bool v = !g_mode1.load();
        g_mode1.store(v);
        led_set(LED1_GPIO, v);
        write_button_state();
    } else if (gpio == BUTTON2_GPIO && pressed) {
        bool v = !g_mode2.load();
        g_mode2.store(v);
        led_set(LED2_GPIO, v);
        write_button_state();
    }
}

// ============================================================================
//  Signal handling
// ============================================================================
static void on_signal(int) { g_running = 0; }

// ============================================================================
//  LCD refresh: show the gesture effect from Python, or a local fallback.
//  Expected /tmp/pi_to_hw_lcd format (1 or 2 lines), e.g.:
//      Filter Cutoff
//      Intensity: 87
//  If the file is missing, show the local mode state.
// ============================================================================
static void refresh_lcd() {
    std::string line1, line2;
    std::ifstream f(LCD_INPUT_FILE);
    if (f) {
        std::getline(f, line1);
        std::getline(f, line2);
    }
    if (line1.empty()) {
        line1 = "M1:" + std::string(g_mode1 ? "ON " : "-- ")
              + " M2:" + std::string(g_mode2 ? "ON" : "--");
    }
    lcd_write_line(0, line1);
    if (LCD_ROWS > 1) lcd_write_line(1, line2);
}

// ============================================================================
//  main
// ============================================================================
int main() {
    // Stop pigpio from hijacking signal handling so our SIGINT works.
    gpioCfgSetInternals(gpioCfgGetInternals() | PI_CFG_NOSIGHANDLER);

    if (gpioInitialise() < 0) {
        fprintf(stderr, "pigpio init failed (run with sudo, Pi 4B only)\n");
        return 1;
    }

    std::signal(SIGINT,  on_signal);
    std::signal(SIGTERM, on_signal);

    // --- inputs: keys + buttons, pull-up, debounced ---
    auto setup_input = [](int gpio) {
        gpioSetMode(gpio, PI_INPUT);
        gpioSetPullUpDown(gpio, PI_PUD_UP);
        gpioGlitchFilter(gpio, 5000);                 // 5 ms debounce
        gpioSetAlertFunc(gpio, gpio_callback);
    };
    for (int i = 0; i < 12; ++i) setup_input(KEY_GPIO[i]);
    setup_input(BUTTON1_GPIO);
    setup_input(BUTTON2_GPIO);

    // --- LEDs off ---
    led_set(LED1_GPIO, false);
    led_set(LED2_GPIO, false);

    // --- LCD ---
    bool lcd_ok = lcd_init();
    if (lcd_ok) {
        lcd_write_line(0, "Gesture MIDI");
        lcd_write_line(1, "Ready");
    }

    // --- MIDI ---
    if (!midi_init()) {
        gpioTerminate();
        return 1;
    }
    midi_autoconnect();

    printf("Hardware controller running. 12 keys live, 2 buttons, LEDs, LCD.\n");
    printf("Press Ctrl+C to quit.\n");
    write_button_state();

    // Main loop just refreshes the LCD; all I/O is interrupt-driven.
    while (g_running) {
        if (lcd_ok) refresh_lcd();
        usleep(150000);   // ~6.6 Hz LCD refresh
    }

    // --- cleanup ---
    printf("\nShutting down...\n");
    for (int i = 0; i < 12; ++i) midi_send_note(BASE_NOTE + i, false); // all notes off
    led_set(LED1_GPIO, false);
    led_set(LED2_GPIO, false);
    if (lcd_ok) {
        lcd_write_line(0, "Stopped");
        lcd_write_line(1, "");
    }
    if (g_lcdHandle >= 0) i2cClose(g_lcdHandle);
    if (g_seq) snd_seq_close(g_seq);
    gpioTerminate();
    return 0;
}
