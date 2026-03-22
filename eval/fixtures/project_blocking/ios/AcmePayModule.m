#import <React/RCTBridgeModule.h>
#import <React/RCTEventEmitter.h>

@interface AcmePayModule : NSObject <RCTBridgeModule>
@property (nonatomic, strong) RCTBridge *bridge;
@end

@implementation AcmePayModule
RCT_EXPORT_MODULE()

RCT_EXPORT_METHOD(initiatePayment:(NSString *)token
                  resolver:(RCTPromiseResolveBlock)resolve
                  rejecter:(RCTPromiseRejectBlock)reject) {
  resolve(@{ @"status": @"pending" });
}

RCT_EXPORT_METHOD(checkPaymentStatus:(NSString *)transactionId
                  resolver:(RCTPromiseResolveBlock)resolve
                  rejecter:(RCTPromiseRejectBlock)reject) {
  resolve(@{ @"status": @"completed" });
}
@end
