export function createWorkletFromSource(workletName: string, workletSource: string) {
  return URL.createObjectURL(
    new Blob([`registerProcessor("${workletName}", ${workletSource})`], {
      type: "application/javascript",
    }),
  );
}

