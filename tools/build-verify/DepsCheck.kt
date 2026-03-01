package com.vanpilot.buildverify

import io.grpc.stub.AbstractStub
import kotlinx.coroutines.CoroutineScope

/** Minimal class to verify Maven dependencies resolve at compile time. */
class DepsCheck {
    fun grpcStubClassName(): String = AbstractStub::class.simpleName ?: "AbstractStub"
    fun coroutineScopeName(): String = CoroutineScope::class.simpleName ?: "CoroutineScope"
}
