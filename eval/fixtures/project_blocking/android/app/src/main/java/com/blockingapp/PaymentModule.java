package com.blockingapp;

import com.facebook.react.bridge.ReactApplicationContext;
import com.facebook.react.bridge.ReactContextBaseJavaModule;
import com.facebook.react.bridge.ReactMethod;
import com.facebook.react.bridge.Promise;
import com.facebook.react.bridge.WritableNativeMap;

public class PaymentModule extends ReactContextBaseJavaModule {

    PaymentModule(ReactApplicationContext context) {
        super(context);
    }

    @Override
    public String getName() {
        return "PaymentModule";
    }

    @ReactMethod
    public void initiatePayment(String token, Promise promise) {
        WritableNativeMap result = new WritableNativeMap();
        result.putString("status", "pending");
        promise.resolve(result);
    }

    @ReactMethod
    public void checkPaymentStatus(String transactionId, Promise promise) {
        promise.resolve(getReactApplicationContext().getPackageName());
    }
}
