import React from 'react';
import { View, NativeModules } from 'react-native';

const { PaymentModule } = NativeModules;

export default function App() {
  const handlePayment = async () => {
    const result = await PaymentModule.initiatePayment('tok_test_123');
    console.log(result);
  };

  return <View />;
}
