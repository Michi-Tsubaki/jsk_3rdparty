uint8 TRANSLATION=1
uint8 ROTATION=2
uint8 SEMANTIC_TRANSLATION=3
uint8 SEMANTIC_ROTATION=4

uint8 kind

# translation: forward/backward/left/right/up/down/positive/negative
# rotation: positive/negative/clockwise/counterclockwise/unspecified
# semantic: away_from_object/toward_object/unspecified
string direction

# x/y/z/unspecified
string axis

bool has_numeric_value
float64 value

# mm/cm/m/deg/rad/none
string unit

# none/tiny/small/medium/large
string qualifier

# Object-relative commands. Empty in the initial numeric implementation.
string target_object_id

# Original text span represented by this segment.
string source_text

bool preserve_orientation
