import { ElMessage as ElementMessage } from "element-plus";

const MESSAGE_DURATION = 2000;

function withDefaultDuration(options: any) {
  if (typeof options === "string") {
    return {
      message: options,
      duration: MESSAGE_DURATION,
    };
  }

  if (options && typeof options === "object") {
    return {
      duration: MESSAGE_DURATION,
      ...options,
    };
  }

  return options;
}

export const ElMessage = Object.assign(
  (options: any) => ElementMessage(withDefaultDuration(options)),
  {
    success: (options: any) => ElementMessage.success(withDefaultDuration(options)),
    warning: (options: any) => ElementMessage.warning(withDefaultDuration(options)),
    error: (options: any) => ElementMessage.error(withDefaultDuration(options)),
    info: (options: any) => ElementMessage.info(withDefaultDuration(options)),
    closeAll: ElementMessage.closeAll,
  },
);
