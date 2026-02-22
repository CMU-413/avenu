import { useCallback, useRef, useState, type ReactNode } from "react";
import ConfirmationDialog from "@/components/ConfirmationDialog";
import { ConfirmDialogContext, type ConfirmDialogOptions } from "@/contexts/confirm-dialog";

const defaultOptions: ConfirmDialogOptions = {
  title: "",
  message: "",
  confirmLabel: "Confirm",
  cancelLabel: "Cancel",
};

export const ConfirmDialogProvider = ({ children }: { children: ReactNode }) => {
  const [options, setOptions] = useState<ConfirmDialogOptions>(defaultOptions);
  const [open, setOpen] = useState(false);
  const resolverRef = useRef<((value: boolean) => void) | null>(null);

  const close = useCallback((value: boolean) => {
    const resolver = resolverRef.current;
    resolverRef.current = null;
    setOpen(false);
    if (resolver) resolver(value);
  }, []);

  const handleConfirm = useCallback(() => {
    options.onConfirm?.();
    close(true);
  }, [close, options]);

  const handleCancel = useCallback(() => {
    options.onCancel?.();
    close(false);
  }, [close, options]);

  const confirm = useCallback((nextOptions: ConfirmDialogOptions) => {
    resolverRef.current?.(false);
    setOptions({
      ...defaultOptions,
      ...nextOptions,
    });
    setOpen(true);
    return new Promise<boolean>((resolve) => {
      resolverRef.current = resolve;
    });
  }, []);

  return (
    <ConfirmDialogContext.Provider value={{ confirm }}>
      {children}
      <ConfirmationDialog
        open={open}
        title={options.title}
        message={options.message}
        confirmLabel={options.confirmLabel}
        cancelLabel={options.cancelLabel}
        onConfirm={handleConfirm}
        onCancel={handleCancel}
      />
    </ConfirmDialogContext.Provider>
  );
};
