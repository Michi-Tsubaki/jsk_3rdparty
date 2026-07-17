uint8 RECEIVED=1
uint8 PARSING=2
uint8 REJECTED=3
uint8 WAITING_APPROVAL=4
uint8 PREFLIGHT=5
uint8 EXECUTING=6
uint8 SUCCEEDED=7
uint8 FAILED=8
uint8 CANCELED=9

std_msgs/Header header
string command_id
uint8 state
string code
string message
bool requires_user_action
uint32 current_segment
uint32 total_segments
