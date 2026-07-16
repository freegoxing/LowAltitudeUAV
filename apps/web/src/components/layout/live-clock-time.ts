export function formatClockTime(date: Date): string {
    return [date.getHours(), date.getMinutes(), date.getSeconds()]
        .map((value) => value.toString().padStart(2, "0"))
        .join(":");
}
