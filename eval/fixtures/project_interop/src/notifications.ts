import { NativeEventEmitter, NativeModules, DeviceEventEmitter } from 'react-native';

const { NotificationModule } = NativeModules;
const emitter = new NativeEventEmitter(NotificationModule);

emitter.addListener('onNotification', (event) => {
  console.log('Notification received:', event);
});

DeviceEventEmitter.addListener('onDeepLink', (url: string) => {
  console.log('Deep link:', url);
});
