/*
 * Copyright (c) 2014 liblcf authors
 * This file is released under the MIT License
 * http://opensource.org/licenses/MIT
 */

#include <cstring>
#include "string_less.h"

bool string_less::operator()(const char *a, const char *b)
{
	return std::strcmp(a, b) < 0;
}

