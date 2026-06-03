class ModeManager:
    def __init__(self):
        self.current_mode = "PLAY"
        self.available_modes = ["PLAY", "EXPRESSION", "DJ"]
        self.gesture_cooldown = 0
        self.COOLDOWN_FRAMES = 30

    def switch_mode(self, target_mode):
        if target_mode in self.available_modes:
            print(f"🔄 Switching to {target_mode} MODE")
            self.current_mode = target_mode
            return True
        return False

    def handle_gesture_switch(self, target_mode):
        if self.gesture_cooldown <= 0:
            self.switch_mode(target_mode)
            self.gesture_cooldown = self.COOLDOWN_FRAMES

    def handle_ui_switch(self, target_mode):
        self.switch_mode(target_mode)

    def tick(self):
        if self.gesture_cooldown > 0:
            self.gesture_cooldown -= 1