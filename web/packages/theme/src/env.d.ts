declare module 'virtual:clinic-site' {
  import type { Clinic, Theme } from '@demo/schema';
  const data: { clinic: Clinic; theme: Theme };
  export default data;
}
