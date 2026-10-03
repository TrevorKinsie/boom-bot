/*
 * bb_exceptions.h - typed exception hierarchy (casino platform).
 *
 * Mirrors boombot/casino/shared/exceptions.py. Every failure mode maps to a
 * dedicated type; the Telegram facade catches CasinoException and renders the
 * user-facing message.
 */
#ifndef BB_EXCEPTIONS_H
#define BB_EXCEPTIONS_H

#include <stdexcept>
#include <string>

namespace bb {

class CasinoException : public std::runtime_error {
public:
    explicit CasinoException(const std::string& message) : std::runtime_error(message) {}
    std::string get_message() const { return what(); }
};

class InsufficientFundsException : public CasinoException {
public:
    explicit InsufficientFundsException(const std::string& message) : CasinoException(message) {}
};

class InvalidBetException : public CasinoException {
public:
    explicit InvalidBetException(const std::string& message) : CasinoException(message) {}
};

class NegativeBetAmountException : public InvalidBetException {
public:
    explicit NegativeBetAmountException(const std::string& message) : InvalidBetException(message) {}
};

class BetExceedsBalanceException : public InvalidBetException {
public:
    explicit BetExceedsBalanceException(const std::string& message) : InvalidBetException(message) {}
};

class UnknownBetTypeException : public InvalidBetException {
public:
    explicit UnknownBetTypeException(const std::string& message) : InvalidBetException(message) {}
};

class BetNotPermittedInPhaseException : public InvalidBetException {
public:
    explicit BetNotPermittedInPhaseException(const std::string& message) : InvalidBetException(message) {}
};

class WalletNotFoundException : public CasinoException {
public:
    explicit WalletNotFoundException(const std::string& message) : CasinoException(message) {}
};

class NegativeMonetaryAmountException : public CasinoException {
public:
    explicit NegativeMonetaryAmountException(const std::string& message) : CasinoException(message) {}
};

class PersistenceException : public CasinoException {
public:
    explicit PersistenceException(const std::string& message) : CasinoException(message) {}
};

class JsonSerializationException : public PersistenceException {
public:
    explicit JsonSerializationException(const std::string& message) : PersistenceException(message) {}
};

class JsonDeserializationException : public PersistenceException {
public:
    explicit JsonDeserializationException(const std::string& message) : PersistenceException(message) {}
};

class ConcurrentModificationException : public PersistenceException {
public:
    explicit ConcurrentModificationException(const std::string& message) : PersistenceException(message) {}
};

class UnsupportedStorageProviderException : public PersistenceException {
public:
    explicit UnsupportedStorageProviderException(const std::string& message) : PersistenceException(message) {}
};

class UnsupportedGameEngineException : public CasinoException {
public:
    explicit UnsupportedGameEngineException(const std::string& message) : CasinoException(message) {}
};

class CommandHandlerResolutionException : public CasinoException {
public:
    explicit CommandHandlerResolutionException(const std::string& message) : CasinoException(message) {}
};

class SagaExecutionException : public CasinoException {
public:
    explicit SagaExecutionException(const std::string& message) : CasinoException(message) {}
};

// Decision engine exceptions (boombot/casino/decisionengine/domain/exceptions.py).
class DecisionEngineUnavailableException : public CasinoException {
public:
    explicit DecisionEngineUnavailableException(const std::string& message) : CasinoException(message) {}
};

class DecisionEngineFailureException : public CasinoException {
public:
    explicit DecisionEngineFailureException(const std::string& message) : CasinoException(message) {}
};

} // namespace bb

#endif // BB_EXCEPTIONS_H
