CC      := gcc
CFLAGS  := -O2 -Wall -Wextra -std=c11 -MMD -MP
TARGET  := read_page
SRC     := src/read_page.c
OBJ     := $(SRC:.c=.o)
DEPS    := $(OBJ:.o=.d)

all: $(TARGET)

$(TARGET): $(OBJ)
	$(CC) $(CFLAGS) -o $@ $^

src/%.o: src/%.c
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(TARGET) $(OBJ) $(DEPS)

-include $(DEPS)
