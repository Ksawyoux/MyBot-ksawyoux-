from enum import Enum

class OutputType(str, Enum):
    RESPONSE = "response"
    STATUS = "status"
    APPROVAL = "approval"
    ERROR = "error"
    NOTIFICATION = "notification"

class TaskCategory(str, Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"
    SCHEDULED = "scheduled"
    SYSTEM = "system"

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_INPUT = "awaiting_input"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_RETRY = "awaiting_retry"

class TransparencyTier(str, Enum):
    SILENT = "silent"
    STANDARD = "standard"
    VERBOSE = "verbose"

class FormatStyle(str, Enum):
    COMPACT = "compact"
    STANDARD = "standard"
    DETAILED = "detailed"

class BlockType(str, Enum):
    TEXT = "text"
    LIST = "list"
    TABLE = "table"
    CARD = "card"
    CODE = "code"
    QUOTE = "quote"
    DIVIDER = "divider"

class ListStyle(str, Enum):
    BULLET = "bullet"
    NUMBERED = "numbered"
    CHECKLIST = "checklist"

class BlockImportance(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"

class ActionType(str, Enum):
    BUTTON = "button"
    LINK = "link"
    CALLBACK = "callback"
    INPUT_PROMPT = "input_prompt"

class ActionStyle(str, Enum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    DANGER = "danger"
    SUCCESS = "success"

class ProgressStyle(str, Enum):
    PERCENTAGE = "percentage"
    STEPS = "steps"
    SPINNER = "spinner"
    ETA = "eta"

class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
