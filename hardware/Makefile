CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall
LIBS     := -lpigpio -lasound -lrt -lpthread
TARGET   := keyboard_controller

$(TARGET): keyboard_controller.cpp
	$(CXX) $(CXXFLAGS) $< -o $@ $(LIBS)

.PHONY: run clean
run: $(TARGET)
	sudo ./$(TARGET)

clean:
	rm -f $(TARGET)
