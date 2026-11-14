// Empty stubs for the TLS init functions create-fself asks for.
//
// Clang emits a weak reference to the "TLS init function" (_ZTH<name>) for every cross-module
// dynamically-referenced extern thread_local, whether or not the variable has dynamic initialization.
// Ultramodern's thread_self and is_game_thread (ultramodern/src/threads.cpp) are initialized with
// constants (nullptr/false), so that translation unit emits no init function and, at link time,
// these references stay weak and undefined. lld resolves those to 0; create-fself rejects a symbol
// it can't attach to a module ("missing module for symbol"). The variables have constant
// initializers, so their init functions would do nothing: these stubs are the whole body.

using void_fn = void();

void stub_thread_self_tls() asm("_ZTH11thread_self");
void stub_game_thread_tls() asm("_ZTH14is_game_thread");

void stub_thread_self_tls() {}
void stub_game_thread_tls() {}
