export function formatDeps(deps: string[], t: (key: string) => string): string {
  const keyMap: [RegExp, string][] = [
    [/Signal Pool/i, 'common.dependencySignalPool'],
    [/Bound to.*Trader/i, 'common.dependencyActiveBinding'],
    [/Program Binding/i, 'common.dependencyProgramBinding'],
    [/AI Strategy/i, 'common.dependencyActiveBinding'],
    [/TriggerConfig/i, 'common.dependencyActiveBinding'],
  ]
  const messages = new Set<string>()
  for (const dep of deps) {
    const match = keyMap.find(([re]) => re.test(dep))
    messages.add(match ? t(match[1]) : dep)
  }
  return Array.from(messages).join(' ')
}
