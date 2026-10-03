package com.boombot.mmo;

/** A user-facing request error carrying an HTTP status code. */
public final class ApiException extends RuntimeException {
    public final int status;

    public ApiException(int status, String message) {
        super(message);
        this.status = status;
    }
}