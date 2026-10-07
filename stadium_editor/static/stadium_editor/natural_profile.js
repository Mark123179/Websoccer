export function naturalProfileFromUpdate({day, floodlight} = {}) {
  if (typeof floodlight === 'boolean') return floodlight ? 'night' : 'day';
  if (typeof day === 'boolean') return day ? 'day' : 'night';
  return null;
}
